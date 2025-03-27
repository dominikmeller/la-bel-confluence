import os
import re
import requests
from requests.auth import HTTPBasicAuth
from collections import Counter
from dotenv import load_dotenv

# 1. Load environment variables from .env
load_dotenv()

CONFLUENCE_URL = os.getenv("CONFLUENCE_URL")             # e.g., https://<your-domain>.atlassian.net/wiki
PAGE_ID = os.getenv("PAGE_ID")                           # e.g., 123456
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME")   # e.g., your-email@example.com
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN") # Your Confluence API token

# 2. Build URL to fetch page content (storage format + version info)
GET_PAGE_URL = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"

def fetch_page():
    """
    Fetch the Confluence page details, including its storage format and version info.
    """
    response = requests.get(
        GET_PAGE_URL,
        auth=HTTPBasicAuth(CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN),
        headers={"Accept": "application/json"}
    )
    response.raise_for_status()
    return response.json()

def extract_color_title_pairs(page_content):
    """
    Extract both 'colour' and 'title' from each status macro, regardless of order.

    Example macro snippet:
      <ac:structured-macro ac:name="status" ...>
        <ac:parameter ac:name="title">Foo</ac:parameter>
        <ac:parameter ac:name="colour">Red</ac:parameter>
      </ac:structured-macro>

    Steps:
    1. Find each entire status macro block with one regex.
    2. Within that block, look separately for the 'colour' parameter and 'title' parameter.
    3. Default color to 'Grey' if no colour parameter is found.
    """
    # 1. Capture the entire content of each status macro
    macro_pattern = r'<ac:structured-macro[^>]+ac:name="status"[^>]*>(.*?)</ac:structured-macro>'
    macro_blocks = re.findall(macro_pattern, page_content, flags=re.DOTALL | re.IGNORECASE)

    color_title_pairs = []
    for block in macro_blocks:
        # 2a. Look for colour parameter
        color_match = re.search(
            r'<ac:parameter[^>]+ac:name="colour"[^>]*>(.*?)</ac:parameter>',
            block,
            flags=re.DOTALL | re.IGNORECASE
        )
        color = color_match.group(1).strip() if color_match else "Grey"

        # 2b. Look for title parameter
        title_match = re.search(
            r'<ac:parameter[^>]+ac:name="title"[^>]*>(.*?)</ac:parameter>',
            block,
            flags=re.DOTALL | re.IGNORECASE
        )
        title = title_match.group(1).strip() if title_match else "Unknown"

        color_title_pairs.append((color, title))

    return color_title_pairs

def build_status_macro(color, title):
    """
    Build a Confluence status macro for the given color and title.
    """
    return (
        f'<ac:structured-macro ac:name="status" ac:schema-version="1">'
        f'<ac:parameter ac:name="colour">{color}</ac:parameter>'
        f'<ac:parameter ac:name="title">{title}</ac:parameter>'
        f'</ac:structured-macro>'
    )

def generate_table_html(status_counts):
    """
    Generate an HTML table in Confluence storage format. Each row displays a status macro
    (with the original color & title) and a count of how many times that pair appears.

    Args:
        status_counts (Counter): Keys are (color, title) tuples; values are counts.
    """
    table_html = (
        "<table>"
        "<thead><tr><th>Status</th><th>Occurrences</th></tr></thead>"
        "<tbody>"
    )

    for (color, title), count in status_counts.items():
        status_macro = build_status_macro(color, title)
        table_html += f"<tr><td>{status_macro}</td><td>{count}</td></tr>"

    table_html += "</tbody></table>"
    return table_html

def update_page(new_table_html):
    """
    Insert or replace the content between <!-- LABEL_TABLE_BEGIN --> and <!-- LABEL_TABLE_END -->.
    If these markers do not exist, append them with the new table at the end of the page content.
    """
    page_data = fetch_page()
    current_version = page_data["version"]["number"]
    current_content = page_data["body"]["storage"]["value"]

    begin_marker = "<!-- LABEL_TABLE_BEGIN -->"
    end_marker = "<!-- LABEL_TABLE_END -->"

    if begin_marker in current_content and end_marker in current_content:
        start_index = current_content.index(begin_marker) + len(begin_marker)
        end_index = current_content.index(end_marker)
        updated_content = (
            current_content[:start_index]
            + "\n" + new_table_html + "\n"
            + current_content[end_index:]
        )
    else:
        # If placeholders aren't found, append them and the table
        new_section = f"\n{begin_marker}\n{new_table_html}\n{end_marker}\n"
        updated_content = current_content + new_section

    # Prepare the JSON payload for the PUT request (incrementing version)
    updated_page = {
        "id": PAGE_ID,
        "type": "page",
        "title": page_data["title"],
        "version": {"number": current_version + 1},
        "body": {
            "storage": {
                "value": updated_content,
                "representation": "storage"
            }
        }
    }

    update_url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}"
    response = requests.put(
        update_url,
        json=updated_page,
        auth=HTTPBasicAuth(CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN),
        headers={"Content-Type": "application/json"}
    )
    response.raise_for_status()
    print("Page updated successfully.")

def main():
    try:
        # 1. Fetch the page content
        page_data = fetch_page()
        page_content = page_data["body"]["storage"]["value"]

        # 2. Extract (color, title) pairs from each status macro
        color_title_pairs = extract_color_title_pairs(page_content)
        if not color_title_pairs:
            print("No status macros found on this page.")
            return

        # 3. Count each unique (color, title) pair
        status_counts = Counter(color_title_pairs)

        # 4. Generate the HTML table with actual color & title macros
        new_table_html = generate_table_html(status_counts)

        # 5. Update the page between placeholders
        update_page(new_table_html)

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
