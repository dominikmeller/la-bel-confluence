#!/usr/bin/env python3
"""
Confluence Decision Log Synchronizer - Enhanced Sync Version

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
    python confluence_decision_sync.py <page_id> <markdown_file_path> [options]

Requirements:
    pip install atlassian-python-api

Configuration:
    Set these environment variables:
    - CONFLUENCE_URL: Your Confluence base URL
    - CONFLUENCE_USERNAME: Your Confluence username (email)
    - CONFLUENCE_API_TOKEN: Your Confluence API token
"""

import re
import os
import sys
import hashlib
import argparse
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime

try:
    from atlassian import Confluence
except ImportError:
    print("❌ Error: atlassian-python-api package not found.")
    print("Please install it with: pip install atlassian-python-api")
    sys.exit(1)

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
        """
        Initialize the Confluence Decision Synchronizer

        Args:
            confluence_url: Base URL of your Confluence instance
            username: Your Confluence username (email)
            api_token: Your Confluence API token
        """
        self.confluence = Confluence(
            url=confluence_url,
            username=username,
            password=api_token,  # API token goes in password field
            cloud=True  # Set to True for Confluence Cloud
        )

        # Test the connection
        try:
            spaces = self.confluence.get_all_spaces(limit=1)
            print(f"✅ Successfully connected to Confluence ({confluence_url})")
        except Exception as e:
            print(f"❌ Failed to connect to Confluence: {e}")
            raise

    def parse_markdown_decisions(self, markdown_content: str) -> List[Decision]:
        """
        Parse markdown content and extract decisions
        Each ## heading becomes a decision title
        Names in [[ ]] become owners
        Content becomes description
        """
        decisions = []

        # Split content by ## headings
        sections = re.split(r'\n## ', markdown_content)

        for i, section in enumerate(sections):
            if i == 0 and not section.startswith('## '):
                # Skip content before first ## heading
                continue

            # Add back the ## if it was split
            if not section.startswith('## '):
                section = '## ' + section

            # Extract title (first line)
            lines = section.split('\n')
            title_line = lines[0]
            title = re.sub(r'^##\s*', '', title_line).strip()

            if not title:
                continue

            # Extract owner from [[ ]] pattern
            owner_match = re.search(r'\[\[([^\]]+)\]\]', section)
            owner = owner_match.group(1) if owner_match else "Unassigned"

            # Extract status from **Status**: pattern
            status_match = re.search(r'\*\*Status\*\*:\s*([^\n]+)', section)
            status = status_match.group(1).strip() if status_match else "OPEN"

            # Extract date from **Date**: pattern
            date_match = re.search(r'\*\*Date\*\*:\s*([^\n]+)', section)
            date_created = date_match.group(1).strip() if date_match else None

            # Get description (everything after title, excluding owner markup)
            description_lines = lines[1:]
            description = '\n'.join(description_lines).strip()
            # Remove owner markup from description
            description = re.sub(r'\[\[[^\]]+\]\]', '', description).strip()

            # Create hash for tracking changes (based on content, not metadata)
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
        """
        Extract existing decisions from a Confluence page
        """
        try:
            page = self.confluence.get_page_by_id(page_id, expand='body.storage')
            content = page['body']['storage']['value']

            decisions = []

            # Extract decision macros from content
            decision_pattern = r'<ac:structured-macro ac:name="decision"[^>]*?ac:macro-id="([^"]*)"[^>]*>(.*?)</ac:structured-macro>'
            matches = re.findall(decision_pattern, content, re.DOTALL)

            for macro_id, macro_content in matches:
                # Extract title
                title_match = re.search(r'<ac:parameter ac:name="title">([^<]*)</ac:parameter>', macro_content)
                title = title_match.group(1) if title_match else f"Decision {macro_id}"

                # Extract owner
                owner_match = re.search(r'<ac:parameter ac:name="owner">([^<]*)</ac:parameter>', macro_content)
                owner = owner_match.group(1) if owner_match else "Unassigned"

                # Extract description from rich text body
                desc_match = re.search(r'<ac:rich-text-body>\s*<p>([^<]*(?:<[^>]*>[^<]*)*)</p>\s*</ac:rich-text-body>', macro_content)
                description = desc_match.group(1) if desc_match else ""

                # Clean up HTML tags from description
                description = re.sub(r'<br/?>', '\n', description)
                description = re.sub(r'<[^>]+>', '', description)
                description = description.strip()

                # Create hash for comparison
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
        """
        Create the XML for a Confluence decision macro
        """
        # Escape HTML characters in content
        def escape_html(text):
            return (text.replace('&', '&amp;')
                       .replace('<', '&lt;')
                       .replace('>', '&gt;')
                       .replace('"', '&quot;')
                       .replace("'", '&#x27;'))

        escaped_description = escape_html(decision.description)
        escaped_owner = escape_html(decision.owner)
        escaped_title = escape_html(decision.title)

        # Convert markdown-style formatting to HTML
        # Bold: **text** -> <strong>text</strong>
        escaped_description = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', escaped_description)
        # Italic: *text* -> <em>text</em>
        escaped_description = re.sub(r'\*(.*?)\*', r'<em>\1</em>', escaped_description)
        # Code: `text` -> <code>text</code>
        escaped_description = re.sub(r'`(.*?)`', r'<code>\1</code>', escaped_description)

        # Convert newlines to <br/> tags for proper HTML rendering
        escaped_description = escaped_description.replace('\n', '<br/>')

        # Add metadata
        if decision.status != "OPEN":
            escaped_description += f'<br/><br/><strong>Status:</strong> {decision.status}'
        if decision.date_created:
            escaped_description += f'<br/><strong>Created:</strong> {decision.date_created}'
        if decision.date_updated:
            escaped_description += f'<br/><strong>Updated:</strong> {decision.date_updated}'

        decision_xml = f"""<ac:structured-macro ac:name="decision" ac:schema-version="1" ac:macro-id="{decision.hash_id}">
    <ac:parameter ac:name="title">{escaped_title}</ac:parameter>
    <ac:parameter ac:name="owner">{escaped_owner}</ac:parameter>
    <ac:rich-text-body>
        <p>{escaped_description}</p>
    </ac:rich-text-body>
</ac:structured-macro>"""

        return decision_xml

    def sync_decisions(self, markdown_decisions: List[Decision], 
                      confluence_decisions: List[Decision]) -> Tuple[List[Decision], SyncResult]:
        """
        Synchronize markdown decisions with existing Confluence decisions
        Returns final decision list and sync result
        """
        sync_result = SyncResult()
        final_decisions = []

        # Create lookup dictionaries
        md_by_title = {d.title: d for d in markdown_decisions}
        conf_by_title = {d.title: d for d in confluence_decisions}

        # Process markdown decisions
        for md_decision in markdown_decisions:
            if md_decision.title in conf_by_title:
                # Decision exists in Confluence, check if it needs updating
                conf_decision = conf_by_title[md_decision.title]
                if md_decision.hash_id != conf_decision.hash_id:
                    # Content has changed, update it
                    md_decision.date_updated = datetime.now().strftime("%Y-%m-%d")
                    final_decisions.append(md_decision)
                    sync_result.updated.append(md_decision.title)
                else:
                    # No changes needed
                    final_decisions.append(conf_decision)
                    sync_result.unchanged.append(md_decision.title)
            else:
                # New decision from markdown
                final_decisions.append(md_decision)
                sync_result.added.append(md_decision.title)

        # Check for decisions only in Confluence (not in markdown)
        for conf_decision in confluence_decisions:
            if conf_decision.title not in md_by_title:
                # Keep existing Confluence-only decisions
                final_decisions.append(conf_decision)
                # Note: We don't add these to any sync result category
                # as they're preserved as-is

        return final_decisions, sync_result

    def create_decisions_page_content(self, decisions: List[Decision], 
                                    page_title: str = "Decision Log",
                                    sync_result: Optional[SyncResult] = None) -> str:
        """
        Create the full page content with all decision macros
        """
        # Get existing page to preserve title
        try:
            existing_page = self.confluence.get_page_by_id(page_title, expand='title')
            actual_title = existing_page['title']
        except:
            actual_title = page_title if isinstance(page_title, str) else "Decision Log"

        header = f"""<h1>{actual_title}</h1>
<p>This page contains all project decisions. It is automatically synchronized with markdown documents.</p>
<p><em>Last synchronized: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</em></p>"""

        if sync_result:
            header += f"""<p><strong>Sync Summary:</strong> 
{len(sync_result.added)} added, {len(sync_result.updated)} updated, 
{len(sync_result.unchanged)} unchanged</p>"""

        header += "<hr/>"

        decision_macros = []
        for decision in decisions:
            decision_xml = self.create_decision_macro_xml(decision)
            decision_macros.append(decision_xml)

        # Add spacing between decisions
        content = header + '\n<br/>\n'.join(decision_macros)

        return content

    def sync_page_with_markdown(self, page_id: str, markdown_file_path: str, 
                               preserve_confluence_only: bool = True) -> SyncResult:
        """
        Synchronize a specific Confluence page with a markdown file

        Args:
            page_id: The Confluence page ID to sync
            markdown_file_path: Path to the markdown file
            preserve_confluence_only: Keep decisions that exist only in Confluence

        Returns:
            SyncResult with details of what was changed
        """
        print(f"🔄 Starting synchronization...")
        print(f"   📄 Page ID: {page_id}")
        print(f"   📝 Markdown: {markdown_file_path}")

        # Read markdown file
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()

        # Parse decisions from markdown
        markdown_decisions = self.parse_markdown_decisions(markdown_content)
        print(f"   📋 Found {len(markdown_decisions)} decisions in markdown")

        # Extract existing decisions from Confluence
        confluence_decisions = self.extract_existing_decisions(page_id)

        # Sync decisions
        final_decisions, sync_result = self.sync_decisions(markdown_decisions, confluence_decisions)

        # Update the page
        try:
            content = self.create_decisions_page_content(final_decisions, page_id, sync_result)

            result = self.confluence.update_page(
                page_id=page_id,
                title=None,  # Keep existing title
                body=content,
                representation='storage'
            )

            page_url = f"{self.confluence.url}/pages/viewpage.action?pageId={page_id}"

            print(f"\n✅ Successfully synchronized page!")
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
    """Main function to run the script"""
    parser = argparse.ArgumentParser(
        description="Synchronize Confluence decision page with markdown file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync markdown file with Confluence page
  python confluence_decision_sync.py 123456789 decisions.md

  # Sync with environment variables set
  export CONFLUENCE_URL='https://your-domain.atlassian.net'
  export CONFLUENCE_USERNAME='your-email@company.com'
  export CONFLUENCE_API_TOKEN='your-api-token'
  python confluence_decision_sync.py 123456789 decisions.md

Required environment variables:
  CONFLUENCE_URL - Your Confluence base URL
  CONFLUENCE_USERNAME - Your Confluence username (email)  
  CONFLUENCE_API_TOKEN - Your Confluence API token
        """
    )

    parser.add_argument('page_id', help='Confluence page ID to sync with')
    parser.add_argument('markdown_file', help='Path to markdown file containing decisions')
    parser.add_argument('--no-preserve', action='store_true', 
                       help='Remove decisions that exist only in Confluence (default: preserve them)')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be changed without making changes')

    args = parser.parse_args()

    # Get configuration from environment variables
    confluence_url = os.getenv('CONFLUENCE_URL')
    username = os.getenv('CONFLUENCE_USERNAME')
    api_token = os.getenv('CONFLUENCE_API_TOKEN')

    # Validate required configuration
    missing_vars = []
    if not confluence_url:
        missing_vars.append('CONFLUENCE_URL')
    if not username:
        missing_vars.append('CONFLUENCE_USERNAME')
    if not api_token:
        missing_vars.append('CONFLUENCE_API_TOKEN')

    if missing_vars:
        print(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("\nSet them like this:")
        for var in missing_vars:
            print(f"  export {var}='your-value-here'")
        sys.exit(1)

    if not os.path.exists(args.markdown_file):
        print(f"❌ Error: Markdown file not found: {args.markdown_file}")
        sys.exit(1)

    try:
        # Initialize the sync tool
        print(f"🔌 Connecting to Confluence...")
        sync = ConfluenceDecisionSync(
            confluence_url=confluence_url,
            username=username,
            api_token=api_token
        )

        if args.dry_run:
            print("🧪 DRY RUN MODE - No changes will be made")
            # TODO: Implement dry run logic
            print("❌ Dry run mode not implemented yet")
            sys.exit(1)

        # Sync the file
        sync_result = sync.sync_page_with_markdown(
            page_id=args.page_id,
            markdown_file_path=args.markdown_file,
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
