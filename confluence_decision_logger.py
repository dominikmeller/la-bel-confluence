#!/usr/bin/env python3
"""
Confluence Decision Log Synchronizer - Logger Version

This script reads a markdown document where each ## heading represents a decision,
extracts decision information including owners (marked as [[Name]]) and descriptions,
and synchronizes a specific Confluence page with the markdown content.

Features:
- Synchronizes with a specific Confluence page ID
- Preserves existing decisions not in markdown
- Updates changed decisions
- Adds new decisions from markdown
- Provides detailed sync report

Usage:
    python confluence_decision_logger.py <markdown_file_path> [--page-id 123456789] [options]
    (If --page-id omitted, the script reads DECISION_PAGE_ID from the environment)

Requirements:
    pip install atlassian-python-api

Configuration:
    Set these environment variables:
    - CONFLUENCE_URL: Your Confluence base URL
    - CONFLUENCE_USERNAME: Your Confluence username (email)
    - CONFLUENCE_API_TOKEN: Your Confluence API token
"""

# NOTE: This file was renamed from `confluence_decision_sync_enhanced.py` to
# `confluence_decision_logger.py` on 2025-08-07. Apart from filename and
# docstring/usage strings, the implementation is unchanged.

import re
import os
import sys
import hashlib
import argparse
from dotenv import load_dotenv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime

# Load variables from a local .env file, if present
load_dotenv()

try:
    from atlassian import Confluence
except ImportError:
    print("❌ Error: atlassian-python-api package not found.")
    print("Please install it with: pip install atlassian-python-api")
    sys.exit(1)

# -- The remainder of the original implementation is unchanged -----------------

@dataclass
class Decision:
    title: str
    owner: str
    description: str
    original_text: str
    hash_id: str
    status: str = "OPEN"  # OPEN, DECIDED, DEFERRED
    date_created: Optional[str] = None
    date_updated: Optional[str] = None
    source: str = "markdown"  # markdown, confluence

    def __post_init__(self):
        if not self.date_created:
            self.date_created = datetime.now().strftime("%Y-%m-%d")

@dataclass
class SyncResult:
    added: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    unchanged: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

class ConfluenceDecisionSync:
    def __init__(self, confluence_url: str, username: str, api_token: str):
        """Initialize the Confluence Decision Synchronizer"""
        self.confluence = Confluence(
            url=confluence_url,
            username=username,
            password=api_token,  # API token goes in password field
            cloud=True  # Set to True for Confluence Cloud
        )
        try:
            spaces = self.confluence.get_all_spaces(limit=1)
            print(f"✅ Successfully connected to Confluence ({confluence_url})")
        except Exception as e:
            print(f"❌ Failed to connect to Confluence: {e}")
            raise

    # The remaining methods are copied verbatim from the original script.

    def parse_markdown_decisions(self, markdown_content: str) -> List[Decision]:
        """Parse markdown content and extract decisions"""
        decisions = []
        sections = re.split(r'\n## ', markdown_content)
        for i, section in enumerate(sections):
            if i == 0 and not section.startswith('## '):
                continue
            if not section.startswith('## '):
                section = '## ' + section
            lines = section.split('\n')
            title_line = lines[0]
            title = re.sub(r'^##\s*', '', title_line).strip()
            if not title:
                continue
            owner_matches = re.findall(r'\[\[([^\]]+)\]\]', section)
            owners = owner_matches if owner_matches else ["Unassigned"]
            owner = ", ".join(owners)            # Look for status in various formats
            status_match = re.search(r'\*\*Status\*\*:\s*([^\n]+)', section)
            if status_match:
                status = status_match.group(1).strip()
            else:
                # Also check for other common status formats
                approved_match = re.search(r'\b(Approved|Accepted|Decided)\b', section, re.IGNORECASE)
                if approved_match:
                    status = "DECIDED"
                elif re.search(r'\b(In Progress|Ongoing)\b', section, re.IGNORECASE):
                    status = "OPEN"
                elif re.search(r'\b(Deferred|Postponed|Planning)\b', section, re.IGNORECASE):
                    status = "DEFERRED"
                else:
                    status = "OPEN"
            date_match = re.search(r'\*\*Date\*\*:\s*([^\n]+)', section)
            date_created = date_match.group(1).strip() if date_match else None
            description_lines = lines[1:]
            description = '\n'.join(description_lines).strip()
            description = re.sub(r'\[\[[^\]]+\]\]', '', description).strip()
            content_for_hash = f"{title}|{owner}|{description}"
            hash_id = hashlib.md5(content_for_hash.encode()).hexdigest()[:8]
            decisions.append(Decision(
                title=title,
                owner=owner,
                description=description,
                original_text=section,
                hash_id=hash_id,
                status=status,
                date_created=date_created,
                source="markdown"
            ))
        return decisions

    def extract_existing_decisions(self, page_id: str) -> List[Decision]:
        try:
            page = self.confluence.get_page_by_id(page_id, expand='body.storage')
            content = page['body']['storage']['value']
            decisions = []
            decision_pattern = r'<ac:structured-macro ac:name="decision"[^>]*?ac:macro-id="([^"]*)"[^>]*>(.*?)</ac:structured-macro>'
            matches = re.findall(decision_pattern, content, re.DOTALL)
            for macro_id, macro_content in matches:
                title_match = re.search(r'<ac:parameter ac:name="title">([^<]*)</ac:parameter>', macro_content)
                title = title_match.group(1) if title_match else f"Decision {macro_id}"
                owner_match = re.search(r'<ac:parameter ac:name="owner">([^<]*)</ac:parameter>', macro_content)
                owner = owner_match.group(1) if owner_match else "Unassigned"
                desc_match = re.search(r'<ac:rich-text-body>\s*<p>([^<]*(?:<[^>]*>[^<]*)*)</p>\s*</ac:rich-text-body>', macro_content)
                description = desc_match.group(1) if desc_match else ""
                description = re.sub(r'<br/?>', '\n', description)
                description = re.sub(r'<[^>]+>', '', description).strip()
                content_for_hash = f"{title}|{owner}|{description}"
                hash_id = hashlib.md5(content_for_hash.encode()).hexdigest()[:8]
                decisions.append(Decision(
                    title=title,
                    owner=owner,
                    description=description,
                    original_text=macro_content,
                    hash_id=hash_id,
                    source="confluence"
                ))
            print(f"📋 Found {len(decisions)} existing decisions in Confluence page")
            return decisions
        except Exception as e:
            print(f"❌ Failed to extract existing decisions: {e}")
            return []

    def create_decision_macro_xml(self, decision: Decision) -> str:
        def escape_html(text):
            return (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;'))
        escaped_description = escape_html(decision.description)
        escaped_owner = escape_html(decision.owner)
        escaped_title = escape_html(decision.title)
        escaped_description = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', escaped_description)
        escaped_description = re.sub(r'\*(.*?)\*', r'<em>\1</em>', escaped_description)
        escaped_description = re.sub(r'`(.*?)`', r'<code>\1</code>', escaped_description)
        escaped_description = escaped_description.replace('\n', '<br/>')
        if decision.date_created:
            escaped_description += f'<br/><strong>Created:</strong> {decision.date_created}'
        if decision.date_updated:
            escaped_description += f'<br/><strong>Updated:</strong> {decision.date_updated}'
        # Map markdown status to Confluence status macro color
        status_color = "Grey"
        if decision.status:
            status_value = decision.status.upper().strip()
            if "APPROVE" in status_value or "DECIDED" in status_value or "ACCEPTED" in status_value:
                status_color = "Green"
            elif "DEFER" in status_value or "POSTPONE" in status_value:
                status_color = "Yellow"
            elif "OPEN" in status_value or "IN PROGRESS" in status_value:
                status_color = "Blue"
            else:
                status_color = "Grey"
        
        # Create a heading with status macro for the decision
        status_macro = f"""<ac:structured-macro ac:name="status" ac:schema-version="1">
    <ac:parameter ac:name=\"colour\">{status_color}</ac:parameter>
    <ac:parameter ac:name=\"title\">{decision.status}</ac:parameter>
</ac:structured-macro>"""
        # Build participants list using @ mentions (plain text)
        participants = ", ".join([name.strip() for name in decision.owner.split(",")])
            
        decision_xml = f"""<h2>{escaped_title}</h2>
<p><strong>Participants:</strong> {participants}</p>
<p>{escaped_description}</p>
<hr/>"""
        return decision_xml

    def sync_decisions(self, markdown_decisions: List[Decision], confluence_decisions: List[Decision]) -> Tuple[List[Decision], SyncResult]:
        sync_result = SyncResult()
        final_decisions = []
        md_by_title = {d.title: d for d in markdown_decisions}
        conf_by_title = {d.title: d for d in confluence_decisions}
        for md_decision in markdown_decisions:
            if md_decision.title in conf_by_title:
                conf_decision = conf_by_title[md_decision.title]
                if md_decision.hash_id != conf_decision.hash_id:
                    md_decision.date_updated = datetime.now().strftime("%Y-%m-%d")
                    final_decisions.append(md_decision)
                    sync_result.updated.append(md_decision.title)
                else:
                    final_decisions.append(conf_decision)
                    sync_result.unchanged.append(md_decision.title)
            else:
                final_decisions.append(md_decision)
                sync_result.added.append(md_decision.title)
        for conf_decision in confluence_decisions:
            if conf_decision.title not in md_by_title:
                final_decisions.append(conf_decision)
        return final_decisions, sync_result

    def create_decisions_page_content(self, decisions: List[Decision], page_id: str, sync_result: Optional[SyncResult] = None) -> str:
        """Create the HTML content for the Confluence page with decisions.
        
        Args:
            decisions: List of Decision objects to include in the page
            page_id: The ID of the Confluence page
            sync_result: Optional SyncResult object with synchronization details
            
        Returns:
            String containing the HTML content for the page
        """
        try:
            existing_page = self.confluence.get_page_by_id(page_id, expand='title')
            actual_title = existing_page['title']
        except:
            actual_title = "Decision Log"
        header = f"""<h1>{actual_title}</h1>
<p>This page contains all project decisions. It is automatically synchronized with markdown documents.</p>
<p><em>Last synchronized: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>"""
        if sync_result:
            header += f"""<p><strong>Sync Summary:</strong> {len(sync_result.added)} added, {len(sync_result.updated)} updated, {len(sync_result.unchanged)} unchanged</p>"""
        header += "<hr/>"
        
        # Sort decisions by date_created (newest first)
        def _parse_date(decision):
            try:
                return datetime.strptime(decision.date_created or "1900-01-01", "%Y-%m-%d")
            except ValueError:
                return datetime(1900, 1, 1)

        sorted_decisions = sorted(decisions, key=_parse_date, reverse=True)        
        decision_sections = [self.create_decision_macro_xml(d) for d in sorted_decisions]
        content = header + '\n'.join(decision_sections)
        return content

    def sync_page_with_markdown(self, page_id: str, markdown_file_path: str, space_key: str, preserve_confluence_only: bool = True) -> SyncResult:
        """Synchronize a Confluence page with decisions from a markdown file.
        
        Args:
            page_id: The ID of the Confluence page to update
            markdown_file_path: Path to the markdown file containing decisions
            space_key: The Confluence space key where the page is located
            preserve_confluence_only: Whether to keep decisions that only exist in Confluence
            
        Returns:
            SyncResult object containing details about the synchronization
        """
        print("🔄 Starting synchronization...")
        print(f"   📄 Page ID: {page_id}")
        print(f"   🏠 Space Key: {space_key}")
        print(f"   📝 Markdown: {markdown_file_path}")
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        markdown_decisions = self.parse_markdown_decisions(markdown_content)
        print(f"   📋 Found {len(markdown_decisions)} decisions in markdown")
        confluence_decisions = self.extract_existing_decisions(page_id)
        final_decisions, sync_result = self.sync_decisions(markdown_decisions, confluence_decisions)
        try:
            content = self.create_decisions_page_content(final_decisions, page_id, sync_result)
            # Get the current page to retrieve its title
            current_page = self.confluence.get_page_by_id(page_id, expand='version')
            page_title = current_page.get('title', 'Decision Log')
            
            # Update the page with the correct parameters
            self.confluence.update_page(
                page_id=page_id,
                title=page_title,
                body=content,
                representation='storage',
                minor_edit=False
            )
            page_url = f"{self.confluence.url}/pages/viewpage.action?pageId={page_id}"
            print("\n✅ Successfully synchronized page!")
            print(f"   🔗 URL: {page_url}")
            print(f"   📊 Total decisions: {len(final_decisions)}")
            if sync_result.added:
                print(f"   ✨ Added: {', '.join(sync_result.added)}")
            if sync_result.updated:
                print(f"   📝 Updated: {', '.join(sync_result.updated)}")
            if sync_result.unchanged:
                print(f"   ➡️  Unchanged: {len(sync_result.unchanged)} decisions")
        except Exception as e:
            print(f"❌ Failed to update page: {e}")
            sync_result.errors.append(str(e))
            raise
        return sync_result

def main():
    """CLI entrypoint for synchronizing Confluence decision pages"""
    parser = argparse.ArgumentParser(
        description="Synchronize Confluence decision page with markdown file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync markdown file with Confluence page
  python confluence_decision_logger.py decisions.md --page-id 123456789

  # Sync with environment variables set
  export CONFLUENCE_URL='https://your-domain.atlassian.net'
  export CONFLUENCE_USERNAME='your-email@company.com'
  export CONFLUENCE_API_TOKEN='your-api-token'
  export DECISION_PAGE_ID='123456789'
  export DECISION_SPACE='SPACEKEY'
  python confluence_decision_logger.py decisions.md
"""
    )
    parser.add_argument('--page-id', help='Confluence page ID to sync with (overrides DECISION_PAGE_ID env var)')
    parser.add_argument('--space-key', help='Confluence space key (overrides DECISION_SPACE env var)')
    parser.add_argument('markdown_file', nargs='?', help='Path to markdown file containing decisions (overrides DECISION_MD_LOCATION env var)')
    parser.add_argument('--no-preserve', action='store_true', help='Remove decisions that exist only in Confluence (default: preserve them)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    args = parser.parse_args()
    confluence_url = os.getenv('CONFLUENCE_URL')
    username = os.getenv('CONFLUENCE_USERNAME')
    api_token = os.getenv('CONFLUENCE_API_TOKEN')
    # Determine the page ID, space key, and markdown file path (CLI args override env vars)
    page_id = args.page_id or os.getenv('DECISION_PAGE_ID')
    space_key = args.space_key or os.getenv('DECISION_SPACE')
    markdown_path = args.markdown_file or os.getenv('DECISION_MD_LOCATION')
    missing_vars = [var for var, val in [
        ('CONFLUENCE_URL', confluence_url),
        ('CONFLUENCE_USERNAME', username),
        ('CONFLUENCE_API_TOKEN', api_token),
        ('DECISION_PAGE_ID', page_id),
        ('DECISION_SPACE', space_key),
        ('DECISION_MD_LOCATION', markdown_path)
    ] if not val]
    if missing_vars:
        print(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
        for var in missing_vars:
            print(f"  export {var}='your-value-here'")
        sys.exit(1)
    if not os.path.exists(markdown_path):
        print(f"❌ Error: Markdown file not found: {markdown_path}")
        sys.exit(1)
    try:
        print("🔌 Connecting to Confluence...")
        sync = ConfluenceDecisionSync(confluence_url=confluence_url, username=username, api_token=api_token)
        if args.dry_run:
            print("🧪 DRY RUN MODE - No changes will be made")
            print("❌ Dry run mode not implemented yet")
            sys.exit(1)
        sync_result = sync.sync_page_with_markdown(
            page_id=page_id,
            markdown_file_path=markdown_path,
            space_key=space_key,
            preserve_confluence_only=not args.no_preserve
        )
        if sync_result.errors:
            print(f"\n⚠️  Completed with {len(sync_result.errors)} errors:")
            for error in sync_result.errors:
                print(f"   • {error}")
            sys.exit(1)
        else:
            print("\n🎉 Synchronization completed successfully!")
    except KeyboardInterrupt:
        print("\n⏹️  Synchronization cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
