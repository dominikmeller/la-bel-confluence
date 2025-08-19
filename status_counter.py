import os
import re
import sys
import requests
from requests.auth import HTTPBasicAuth
from collections import Counter
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs

# 1. Load environment variables from .env
load_dotenv()

CONFLUENCE_URL = os.getenv("CONFLUENCE_URL")             # e.g., https://<your-domain>.atlassian.net/wiki
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME")   # e.g., your-email@example.com
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN") # Your Confluence API token

# Get page ID from environment variable or command line argument
PAGE_ID = os.getenv("PAGE_ID")
PAGE_URL = os.getenv("PAGE_URL")

def get_page_id():
    """
    Get the page ID from environment variables, command line arguments, or by parsing a URL.
    """
    global PAGE_ID

    # Check if PAGE_ID is already set
    if PAGE_ID:
        return PAGE_ID

    # Check if a URL was provided in environment variables
    if PAGE_URL:
        page_id = extract_page_id_from_url(PAGE_URL)
        if page_id:
            PAGE_ID = page_id
            return PAGE_ID

    # Check command line arguments
    if len(sys.argv) > 1:
        # If argument looks like a URL
        if sys.argv[1].startswith('http'):
            page_id = extract_page_id_from_url(sys.argv[1])
            if page_id:
                PAGE_ID = page_id
                return PAGE_ID
        else:
            # Assume the argument is a page ID
            PAGE_ID = sys.argv[1]
            return PAGE_ID

    # If we get here, we couldn't determine the page ID
    print("Error: No page ID provided.")
    print("Please provide a page ID or URL in one of the following ways:")
    print("1. Set PAGE_ID environment variable")
    print("2. Set PAGE_URL environment variable")
    print("3. Pass page ID as command line argument: python status_counter.py 88342541")
    print("4. Pass page URL as command line argument: python status_counter.py https://digital-advantics.atlassian.net/wiki/spaces/HSPDev/pages/88342541/Sites+Configuration+PIM+Servers")
    sys.exit(1)

def extract_page_id_from_url(url):
    """
    Extract the page ID from a Confluence URL.
    """
    # Pattern for URLs like .../pages/88342541/...
    page_id_match = re.search(r'/pages/(\d+)/', url)
    if page_id_match:
        return page_id_match.group(1)

    # Try to parse as query parameter
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    if 'pageId' in query_params:
        return query_params['pageId'][0]

    return None

# Get the page ID and build the URL to fetch page content
PAGE_ID = get_page_id()
GET_PAGE_URL = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"

def fetch_page():
    """
    Fetch the Confluence page details, including its storage format and version info.
    """
    if not CONFLUENCE_USERNAME or not CONFLUENCE_API_TOKEN:
        raise ValueError("CONFLUENCE_USERNAME and CONFLUENCE_API_TOKEN must be set")

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
      1. Capture each status macro block.
      2. Within that block, search for 'colour' and 'title' parameters.
      3. Default color to 'Grey' if no colour parameter is found.
    """
    macro_pattern = r'<ac:structured-macro[^>]+ac:name="status"[^>]*>(.*?)</ac:structured-macro>'
    macro_blocks = re.findall(macro_pattern, page_content, flags=re.DOTALL | re.IGNORECASE)

    color_title_pairs = []
    for block in macro_blocks:
        color_match = re.search(
            r'<ac:parameter[^>]+ac:name="colour"[^>]*>(.*?)</ac:parameter>',
            block,
            flags=re.DOTALL | re.IGNORECASE
        )
        color = color_match.group(1).strip() if color_match else "Grey"

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
    Generate an HTML table in Confluence storage format.

    First section: rows for each (color, title) pair and its occurrence.
    Second section: aggregated totals by color (ignoring text), with each row displaying
    a status macro (using the color for both parameters) and the total count for that color.

    The table renders at its default (normal) width.

    Args:
        status_counts (Counter): Keys are (color, title) tuples; values are counts.
    """
    table_html = (
        "<table>"
        "<thead><tr><th>Status</th><th>Occurrences</th></tr></thead>"
        "<tbody>"
    )

    # Section 1: Rows by (color, title) pair
    for (color, title), count in status_counts.items():
        status_macro = build_status_macro(color, title)
        table_html += f"<tr><td>{status_macro}</td><td>{count}</td></tr>"

    # Separator row for aggregated totals by color
    table_html += '<tr><td colspan="2"><strong>Total by Color</strong></td></tr>'

    # Aggregate counts by color (disregarding the text)
    aggregated_color_counts = {}
    for (color, title), count in status_counts.items():
        aggregated_color_counts[color] = aggregated_color_counts.get(color, 0) + count

    # Section 2: Rows for each color aggregate
    for color, agg_count in aggregated_color_counts.items():
        # Use the color as both the status text and color in the macro
        status_macro = build_status_macro(color, color)
        table_html += f"<tr><td>{status_macro}</td><td>{agg_count}</td></tr>"

    table_html += "</tbody></table>"
    return table_html

def update_page(new_table_html):
    """
    Insert or replace the content between <!- LABEL_TABLE_BEGIN !> and <!- LABEL_TABLE_END -!>.
    If these markers do not exist, append them with the new table at the end of the page content.
    """
    page_data = fetch_page()
    current_version = page_data["version"]["number"]
    current_content = page_data["body"]["storage"]["value"]

    begin_marker = "<!- LABEL_TABLE_BEGIN -!>"
    end_marker = "<!- LABEL_TABLE_END -!>"

    if begin_marker in current_content and end_marker in current_content:
        start_index = current_content.index(begin_marker) + len(begin_marker)
        end_index = current_content.index(end_marker)
        updated_content = (
            current_content[:start_index]
            + "\n" + new_table_html + "\n"
            + current_content[end_index:]
        )
    else:
        new_section = f"\n{begin_marker}\n{new_table_html}\n{end_marker}\n"
        updated_content = current_content + new_section

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
        print(f"Processing Confluence page with ID: {PAGE_ID}")
        print(f"Using URL: {GET_PAGE_URL}")

        page_data = fetch_page()
        page_content = page_data["body"]["storage"]["value"]

        color_title_pairs = extract_color_title_pairs(page_content)
        if not color_title_pairs:
            print("No status macros found on this page.")
            return

        status_counts = Counter(color_title_pairs)
        print(f"Found {sum(status_counts.values())} status macros with {len(status_counts)} unique color/title combinations")

        new_table_html = generate_table_html(status_counts)
        update_page(new_table_html)

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Error: Page with ID {PAGE_ID} not found. Please check if the page ID is correct.")
        elif e.response.status_code == 401 or e.response.status_code == 403:
            print("Error: Authentication failed. Please check your Confluence username and API token.")
        else:
            print(f"HTTP Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
