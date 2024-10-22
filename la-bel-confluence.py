import os
from atlassian import Confluence
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Fetch environment variables
CONFLUENCE_URL = os.getenv('CONFLUENCE_URL')
CONFLUENCE_USERNAME = os.getenv('CONFLUENCE_USERNAME')
CONFLUENCE_API_TOKEN = os.getenv('CONFLUENCE_API_TOKEN')
CONFLUENCE_SPACE_KEY = os.getenv('CONFLUENCE_SPACE_KEY')

# Initialize Confluence client
class ConfluenceLabelManager:
    def __init__(self):
        self.confluence = Confluence(
            url=CONFLUENCE_URL,
            username=CONFLUENCE_USERNAME,
            password=CONFLUENCE_API_TOKEN
        )
        self.space_key = CONFLUENCE_SPACE_KEY
        self.labeled_pages = []  # To keep track of all pages labeled during the process

    def list_top_level_pages(self):
        try:
            pages = self.confluence.get_all_pages_from_space(self.space_key, start=0, limit=1000)
            if not pages:
                print("No pages found.")
                return []
            return pages
        except Exception as e:
            print(f"Error fetching pages: {e}")
            return []

    def add_label_to_page(self, page_id, label):
        try:
            response = self.confluence.set_page_label(page_id, label)
            if response:
                page_info = self.confluence.get_page_by_id(page_id)
                self.labeled_pages.append(page_info['title'])  # Add title of the page to labeled_pages
                print(f"Label '{label}' added to page {page_info['title']} (ID: {page_id}).")
            else:
                print(f"Failed to add label to page {page_id}.")
        except Exception as e:
            print(f"Error adding label: {e}")

    def cascade_labels(self, top_level_page, label):
        # Add label to the top-level page
        self.add_label_to_page(top_level_page['id'], label)

        # Recursively add label to all child pages
        self.add_labels_to_children(top_level_page['id'], label)

    def add_labels_to_children(self, page_id, label):
        try:
            children = self.confluence.get_page_child_by_type(page_id, type='page', start=0, limit=1000)
            if not children:
                return

            for child in children:
                # Add label to each child page
                self.add_label_to_page(child['id'], label)
                
                # Recursively add labels to this child's children
                self.add_labels_to_children(child['id'], label)
        except Exception as e:
            print(f"Error fetching child pages for page {page_id}: {e}")

    def list_labeled_pages(self):
        print("\nPages that were given the new label:")
        for title in self.labeled_pages:
            print(f"- {title}")

if __name__ == "__main__":
    label_manager = ConfluenceLabelManager()

    # List top-level pages
    top_level_pages = label_manager.list_top_level_pages()
    if not top_level_pages:
        print("No top-level pages to label.")
        exit()

    # Display pages for selection
    for i, page in enumerate(top_level_pages):
        print(f"{i}: {page['title']}")

    # Get user input for page and label
    selected_page_index = int(input("Enter the number of the top-level page you want to label: "))
    label = input("Enter the label you want to add: ")

    # Validate user input
    if 0 <= selected_page_index < len(top_level_pages):
        selected_page = top_level_pages[selected_page_index]
        label_manager.cascade_labels(selected_page, label)
        # List all pages that were labeled during the process
        label_manager.list_labeled_pages()
    else:
        print("Invalid page selection.")
