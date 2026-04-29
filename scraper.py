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
    #check if the current URL itself is valid before doing anything
    if not is_valid(url):
        return []
    
    #defragment and check if page has been seen before 
    defrag_url, _ = urldefrag(url)
    if defrag_url in unique_pages:
        return []
    
    #only now do the expensive parsing
    links = extract_next_links(defrag_url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    #validate response
    if resp.status != 200 or resp.raw_response is None:
        return []
    
    content_type = resp.raw_response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return []
    
    #defragment and record the URL as a unique page
    defrag_url, _ = urldefrag(url)
    
    if defrag_url in unique_pages:
        return []
    unique_pages.add(defrag_url)
    
    #track subdomains for ics.uci.edu
    parsed_url = urlparse(defrag_url)
    hostname = parsed_url.hostname  # e.g. vision.ics.uci.edu
    if hostname and hostname.endswith(".uci.edu"):
        # Extract just the subdomain portion
        subdomains[hostname].add(defrag_url)
    
    #parse the HTML
    soup = BeautifulSoup(resp.raw_response.content, "lxml")
    
    #extract and count words for report
    text = soup.get_text()
    #only words with 2+ letters
    words = re.findall(r"[a-zA-Z]{2,}", text.lower()) 
    filtered_words = [w for w in words if w not in STOP_WORDS]
    
    word_count = len(words)
    
    #update longest page
    if word_count > longest_page["word_count"]:
        longest_page["url"] = defrag_url
        longest_page["word_count"] = word_count
    
    #update global word frequencies
    for word in filtered_words:
        word_frequencies[word] += 1
    
    #extract and return all valid links
    found_links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        #make relative URLs absolute
        absolute_url = urljoin(defrag_url, href)
        #remove fragment
        clean_url, _ = urldefrag(absolute_url)
        found_links.append(clean_url)
    
    return found_links


#makes sure that the URL is valid and within the allowed domains, and does not point to non-content files
def is_valid(url):
    try:
        parsed = urlparse(url)
        
        if parsed.scheme not in {"http", "https"}:
            return False
        
        #must be within the allowed domains
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
        
        #block non-content file extensions
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
