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

# Check if any environment variable is missing and prompt for input if necessary
if not CONFLUENCE_URL:
    CONFLUENCE_URL = input("Enter the Confluence URL (e.g. https://{name}.atlassian.net/wiki): ")
if not CONFLUENCE_USERNAME:
    CONFLUENCE_USERNAME = input("Enter your Confluence username: ")

# Initialize Confluence client
class ConfluenceLabelManager:
    def __init__(self):
        try:
            self.confluence = Confluence(
                url=CONFLUENCE_URL,
                username=CONFLUENCE_USERNAME,
                password=CONFLUENCE_API_TOKEN
            )
            self.space_key = CONFLUENCE_SPACE_KEY
            self.labeled_pages = []  # To keep track of all pages labeled during the process
        except Exception as e:
            print(f"Error initializing Confluence client: {e}")
            exit(1)

    def list_top_level_pages(self):
        try:
            pages = self.confluence.get_all_pages_from_space(self.space_key, start=0, limit=1000)
            if not pages:
                print("No pages found in the specified space.")
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
                self.labeled_pages.append(page_info['title'])
                print(f"Label '{label}' added to page '{page_info['title']}' (ID: {page_id}).")
            else:
                print(f"Failed to add label '{label}' to page (ID: {page_id}).")
        except Exception as e:
            print(f"Error adding label '{label}' to page (ID: {page_id}): {e}")

    def cascade_labels(self, top_level_page, labels):
        print(f"\nAdding labels to '{top_level_page['title']}' and its child pages...")
        labels = labels.split()  # Split the input string into a list of labels
        for label in labels:
            self.add_label_to_page(top_level_page['id'], label)
        self.add_labels_to_children(top_level_page['id'], labels)

    def add_labels_to_children(self, page_id, labels):
        try:
            children = self.confluence.get_page_child_by_type(page_id, type='page', start=0, limit=1000)
            if not children:
                return

            for child in children:
                for label in labels:
                    self.add_label_to_page(child['id'], label)
                self.add_labels_to_children(child['id'], labels)
        except Exception as e:
            print(f"Error fetching child pages for page (ID: {page_id}): {e}")

    def list_labeled_pages(self):
        print("\nPages that were given the new label(s):")
        for title in self.labeled_pages:
            print(f"- {title}")

    def get_all_labels(self):
        try:
            all_labels = {}
            start = 0
            limit = 200
            while True:
                url = f"rest/api/content?spaceKey={self.space_key}&expand=metadata.labels&start={start}&limit={limit}"
                response = self.confluence.get(url)
                
                if not response or 'results' not in response:
                    break
                
                for content in response['results']:
                    labels = content.get('metadata', {}).get('labels', {}).get('results', [])
                    for label in labels:
                        label_id = label.get('id')
                        label_name = label.get('name')
                        if label_id and label_name:
                            key = f"{label_id}:{label_name}"
                            all_labels[key] = all_labels.get(key, 0) + 1
                
                if len(response['results']) < limit:
                    break
                
                start += limit

            return all_labels
        except Exception as e:
            print(f"Error fetching labels: {e}")
            return {}

    def list_labels_sorted(self):
        all_labels = self.get_all_labels()
        sorted_labels = sorted(all_labels.items(), key=lambda x: x[1], reverse=True)
        print("\nAll labels sorted by occurrence:")
        for i, (label_key, count) in enumerate(sorted_labels, 1):
            label_id, label_name = label_key.split(':', 1)
            print(f"{i}. {label_name}, ID: {label_id}, Count: {count}")
        return sorted_labels

    def remove_label_from_all_pages(self, label_id, label_name):
        try:
            start = 0
            limit = 200
            removed_count = 0
            while True:
                url = f"rest/api/content?spaceKey={self.space_key}&expand=metadata.labels&start={start}&limit={limit}"
                response = self.confluence.get(url)
                
                if not response or 'results' not in response:
                    break
                
                for content in response['results']:
                    content_id = content['id']
                    labels = content.get('metadata', {}).get('labels', {}).get('results', [])
                    for label in labels:
                        if label.get('id') == label_id and label.get('name') == label_name:
                            self.confluence.remove_page_label(content_id, label_name)
                            removed_count += 1
                            print(f"Removed label '{label_name}' from page {content['title']} (ID: {content_id})")
                
                if len(response['results']) < limit:
                    break
                
                start += limit

            print(f"\nTotal labels removed: {removed_count}")
        except Exception as e:
            print(f"Error removing labels: {e}")

def get_user_action():
    while True:
        action = input("Do you want to (A)dd or (R)emove labels? ").lower()
        if action in ['a', 'r']:
            return action
        print("Invalid choice. Please enter 'A' for Add or 'R' for Remove.")

if __name__ == "__main__":
    label_manager = ConfluenceLabelManager()
    action = get_user_action()

    if action == 'a':
        # Existing functionality for adding labels
        top_level_pages = label_manager.list_top_level_pages()
        if not top_level_pages:
            print("No top-level pages to label.")
            exit()

        # Display pages for selection
        for i, page in enumerate(top_level_pages):
            print(f"{i}: {page['title']}")

        # Get user input for page and labels
        selected_page_index = int(input("Enter the number of the top-level page you want to label: "))
        labels = input("Enter the label(s) you want to add (separate multiple labels with spaces): ")

        # Validate user input
        if 0 <= selected_page_index < len(top_level_pages):
            selected_page = top_level_pages[selected_page_index]
            label_manager.cascade_labels(selected_page, labels)
            # List all pages that were labeled during the process
            label_manager.list_labeled_pages()
        else:
            print("Invalid page selection.")
    
    elif action == 'r':
        print("Listing all labels in the Confluence space...")
        sorted_labels = label_manager.list_labels_sorted()
        if not sorted_labels:
            print("No labels found in the Confluence space.")
        else:
            while True:
                try:
                    label_index = int(input("\nEnter the number of the label you want to remove (or 0 to exit): ")) - 1
                    if label_index == -1:
                        break
                    if 0 <= label_index < len(sorted_labels):
                        label_key, _ = sorted_labels[label_index]
                        label_id, label_name = label_key.split(':', 1)
                        confirm = input(f"Are you sure you want to remove the label '{label_name}' from all pages? (y/n): ")
                        if confirm.lower() == 'y':
                            label_manager.remove_label_from_all_pages(label_id, label_name)
                        break
                    else:
                        print("Invalid label number. Please try again.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
