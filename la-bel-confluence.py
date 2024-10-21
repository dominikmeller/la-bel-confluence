import os
from dotenv import load_dotenv
from atlassian import Confluence

# Load environment variables from the .env file
load_dotenv()

class ConfluenceLabelManager:
    def __init__(self):
        self.confluence = Confluence(
            url=os.getenv('CONFLUENCE_URL'), 
            username=os.getenv('CONFLUENCE_USERNAME'), 
            password=os.getenv('CONFLUENCE_API_TOKEN')
        )
        self.space_key = os.getenv('CONFLUENCE_SPACE_KEY')

    def list_top_level_pages(self):
        pages = self.confluence.get_all_pages_from_space(self.space_key, start=0, limit=1000)
        top_level_pages = [page for page in pages if not page.get("ancestors")]
        return top_level_pages

    def list_child_pages(self, page_id):
        children = self.confluence.get_page_child_by_type(page_id, type="page", start=0, limit=1000)
        return children

    def get_labels_for_page(self, page_id):
        labels = self.confluence.get_page_labels(page_id)
        print(f"Labels for page {page_id}: {labels}")  # Debugging step
        if isinstance(labels, dict) and 'results' in labels:
            return labels['results']
        else:
            print(f"Unexpected label format for page {page_id}: {labels}")
            return []

    def add_label_to_page(self, page_id, label):
        # Prepare the URL
        url = f"{self.confluence.url}/rest/api/content/{page_id}/label"

        # Prepare the data for the label
        data = [{"prefix": "global", "name": label}]
        
        # Make the POST request to add the label
        response = self.confluence.post(url, json=data)
        
        # Check if the response is successful
        if response.status_code == 200:
            print(f"Label '{label}' added to page {page_id}.")
        else:
            print(f"Failed to add label '{label}' to page {page_id}. Response: {response.text}")

    def cascade_labels(self, top_level_page, label):
        self.add_label_to_page(top_level_page['id'], label)
        child_pages = self.list_child_pages(top_level_page['id'])
        for child_page in child_pages:
            self.add_label_to_page(child_page['id'], label)
            self.cascade_labels(child_page, label)


# Main logic
if __name__ == "__main__":
    label_manager = ConfluenceLabelManager()

    # Step 1: List top-level pages
    top_level_pages = label_manager.list_top_level_pages()

    # Step 2: Present top-level pages for selection
    print("Select a top-level page by number:")
    for idx, page in enumerate(top_level_pages):
        print(f"{idx}: {page['title']}")

    selected_index = int(input("Enter the number of the top-level page you want to label: "))
    selected_page = top_level_pages[selected_index]

    # Step 3: Get label input from user
    label = input("Enter the label you want to add: ")

    # Step 4: Add the label to the selected top-level page and cascade it down to child pages
    label_manager.cascade_labels(selected_page, label)

