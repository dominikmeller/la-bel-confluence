# la-bel-confluence or How to bulk add labels to Confluence pages?

## The Story

I needed to label some Confluence pages to prepare my space for RAG (Retrieval-Augmented Generation), and honestly, I wasn't in the mood to click through endless Confluence menus. So, staying true to my API-first nature, I wrote this script called **la-bel-confluence** to help manage the process easily and programmatically.

Now, instead of manually adding labels one by one, this script does all the heavy lifting for me, cascading labels to all child pages automatically. It's perfect if you, like me, want to get things done with minimal effort.

## What Does It Do?

**la-bel-confluence** is a Python script that:

- Adds labels to a selected Confluence page.
- Propagates those labels to all child pages.
- Allows you to add multiple labels by using spaces.

It's designed to either configure itself using a `.env` file or ask for your credentials interactively, making it very easy to set up and use.

## How to Use It

1. **Clone the Repository**

   Clone the repo from GitHub:

   ```sh
   git clone https://github.com/dominikmeller/la-bel-confluence.git
   cd la-bel-confluence
   ```

2. **Set Up the Environment**

   Install the necessary Python dependencies:

   ```sh
   pip install -r requirements.txt
   ```

3. **Configuration**

   You can configure the script via a `.env` file, which should contain the following variables:

   ```env
   CONFLUENCE_URL=https://your-confluence-url.com/
   CONFLUENCE_USERNAME=your_username
   CONFLUENCE_API_TOKEN=your_api_token
   CONFLUENCE_SPACE_KEY=your_space_key
   ```

   If a `.env` file isn't available, no worries! The script will ask for your Confluence credentials interactively the first time you run it. This way, you can still run it without any setup if you're not comfortable with environment files.

4. **Run the Script**

   Run the script with:

   ```sh
   python la-bel-confluence.py
   ```

   - You'll be prompted to select a top-level page from your Confluence space.
   - Enter the label you want to add.
   - You can add multiple labels by separating them with a space.
   
5. **Label Cascade**

   After selecting a page, the script will apply the specified labels to the page and then propagate them to all its child pages. At the end of the process, it will also list all the pages that received the new label(s).

## Contributing

Feel free to fork the repository and create pull requests if you have ideas for improvements. Any feedback is welcome.

**Repo URL**: [la-bel-confluence on GitHub](https://github.com/dominikmeller/la-bel-confluence)

## License

MIT License. Do whatever you want, but please don't blame me if Confluence gets angry about too many API calls ;)

## New Feature: Label Removal

In addition to adding labels, this script now allows you to remove labels from all pages in a Confluence space:

1. Run the script and choose 'R' when prompted to remove labels.
2. The script will display a list of all labels in the Confluence space, sorted by occurrence.
3. Enter the number corresponding to the label you want to remove.
4. Confirm the removal when prompted.
5. The script will remove the selected label from all pages in the space.

**Caution**: The label removal feature will remove the selected label from ALL pages in the specified Confluence space. Use this feature with care.

---

Enjoy automating Confluence without leaving your terminal!

