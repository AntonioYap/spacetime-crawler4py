import re
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup
from collections import defaultdict


#global data structures for report
unique_pages = set()
word_frequencies = defaultdict(int)
longest_page = {"url": "", "word_count": 0}
subdomains = defaultdict(set)

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't",
    "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "get", "got",
    "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's",
    "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its",
    "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of",
    "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over",
    "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
    "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "will", "with",
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}

def scraper(url, resp):
    # check if the current URL itself is valid before doing anything
    if not is_valid(url):
        return []
    
    # defragment and check if page has been seen before
    defrag_url, _ = urldefrag(url)
    if defrag_url in unique_pages:
        return []
    unique_pages.add(defrag_url)

    # print progress every 50 pages
    if len(unique_pages) % 50 == 0:
        print(f"Progress: {len(unique_pages)} pages crawled")

    # only now do the expensive parsing
    links = extract_next_links(defrag_url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    if resp.status != 200 or not resp.raw_response:
        return []
    
    content_type = resp.raw_response.headers.get("Content-Type", "").lower()

    # validate response, avoid xml traps and non-html files
    if "text/html" not in content_type or "xml" in content_type:
        return []

    # track subdomains for uci.edu
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    if hostname and hostname.endswith(".uci.edu"):
        subdomains[hostname].add(url)

    try:
        # parse the HTML
        soup = BeautifulSoup(resp.raw_response.content, "lxml")

        # extract and count words for report
        text = soup.get_text()
        # only words with 2+ letters
        words = re.findall(r"[a-zA-Z]{2,}", text.lower())

        # update longest page
        if len(words) > longest_page["word_count"]:
            longest_page["url"] = url
            longest_page["word_count"] = len(words)

        # update global word frequencies
        for word in words:
            if word not in STOP_WORDS:
                word_frequencies[word] += 1

        # extract and return all valid links
        found_links = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            absolute_url = urljoin(url, href)
            clean_url, _ = urldefrag(absolute_url)
            found_links.append(clean_url)

        return found_links

    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return []

def is_valid(url):
    try:
        parsed = urlparse(url)
        url_lower = url.lower()

        if parsed.scheme not in {"http", "https"}:
            return False

        # must be within the allowed domains
        hostname = parsed.hostname
        if not hostname:
            return False

        allowed_domains = [
            ".ics.uci.edu",
            ".cs.uci.edu",
            ".informatics.uci.edu",
            ".stat.uci.edu"
        ]

        if not any(hostname.endswith(domain) for domain in allowed_domains):
            return False

        # --- TRAP FILTERING SECTION ---

        # block common path traps
        path_lower = parsed.path.lower()
        if any(x in path_lower for x in ["doku.php", "ical", "tribe", "events", "pix"]):
            return False

        # block repeat directory traps (e.g., /folder/folder/folder/)
        if re.match(r"^.*?(.+?/).*?\1.*?\1.*$", path_lower):
            return False

        # block grape.ics
        if "grape.ics.uci.edu" in hostname:
            return False

        # block subdomains for calendars/dynamic content
        if any(sub in hostname for sub in ["wics.ics.uci.edu", "ngs.ics.uci.edu"]):
            return False

        # block authentication and session-related keywords
        if any(x in url_lower for x in ["auth", "login", "signup", "signin", "logout"]):
            return False

        # block extremely long query strings
        if len(parsed.query) > 100:
            return False

        # block non-content file extensions
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$",
            parsed.path.lower()
        )

    except TypeError:
        print("TypeError for", parsed)
        raise

def print_report():
    print(f"\n--- CRAWLER REPORT ---")

    print(f"\n1. Unique pages found: {len(unique_pages)}")

    print(f"\n2. Longest page: {longest_page['url']} ({longest_page['word_count']} words)")

    print(f"\n3. Top 50 most common words:")
    sorted_words = sorted(word_frequencies.items(), key=lambda x: x[1], reverse=True)
    for word, count in sorted_words[:50]:
        print(f"   {word}: {count}")

    print(f"\n4. Subdomains ({len(subdomains)} total):")
    for subdomain in sorted(subdomains.keys()):
        print(f"   {subdomain}, {len(subdomains[subdomain])}")