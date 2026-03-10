import tkinter as tk
from tkinter import ttk, scrolledtext
import requests
import threading
from urllib.parse import quote
import time

class UsernameFinder:
    def __init__(self, root):
        self.root = root
        self.root.title("Username Finder - Search Across Platforms")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Platform URLs - using direct profile URL patterns
        self.platforms = {
            'GitHub': 'https://github.com/{}',
            'Twitter/X': 'https://twitter.com/{}',
            'Instagram': 'https://www.instagram.com/{}/',
            'Reddit': 'https://www.reddit.com/user/{}',
            'TikTok': 'https://www.tiktok.com/@{}',
            'YouTube': 'https://www.youtube.com/@{}',
            'LinkedIn': 'https://www.linkedin.com/in/{}',
            'Pinterest': 'https://www.pinterest.com/{}/',
            'Medium': 'https://medium.com/@{}',
            'Twitch': 'https://www.twitch.tv/{}',
            'Spotify': 'https://open.spotify.com/user/{}',
            'SoundCloud': 'https://soundcloud.com/{}',
            'DeviantArt': 'https://www.deviantart.com/{}',
            'Behance': 'https://www.behance.net/{}',
            'Dribbble': 'https://dribbble.com/{}',
            'Vimeo': 'https://vimeo.com/{}',
            'Tumblr': 'https://{}.tumblr.com',
            'Flickr': 'https://www.flickr.com/people/{}',
            'Patreon': 'https://www.patreon.com/{}',
            'Ko-fi': 'https://ko-fi.com/{}',
        }
        
        self.is_searching = False
        self.setup_ui()
        
    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Username Finder", 
                               font=('Helvetica', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, 10))
        
        # Input frame
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)
        
        ttk.Label(input_frame, text="Username:").grid(row=0, column=0, padx=(0, 10))
        
        self.username_entry = ttk.Entry(input_frame, font=('Helvetica', 11))
        self.username_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.username_entry.bind('<Return>', lambda e: self.start_search())
        
        self.search_button = ttk.Button(input_frame, text="Search", command=self.start_search)
        self.search_button.grid(row=0, column=2)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Results area
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding="10")
        results_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        self.results_text = scrolledtext.ScrolledText(results_frame, 
                                                      wrap=tk.WORD, 
                                                      font=('Courier', 10),
                                                      height=20)
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure text tags for formatting
        self.results_text.tag_configure("found", foreground="green", font=('Courier', 10, 'bold'))
        self.results_text.tag_configure("notfound", foreground="red")
        self.results_text.tag_configure("error", foreground="orange")
        self.results_text.tag_configure("link", foreground="blue", underline=True)
        self.results_text.tag_configure("header", font=('Courier', 11, 'bold'))
        
        # Status bar
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
    def update_status(self, message):
        self.status_label.config(text=message)
        
    def check_username(self, platform, url_template, username):
        """Check if username exists on a platform"""
        url = url_template.format(username)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            
            # Check status code
            if response.status_code == 200:
                return 'found', url
            elif response.status_code == 404:
                return 'notfound', url
            else:
                return 'unknown', url
                
        except requests.RequestException as e:
            return 'error', url
            
    def search_platforms(self, username):
        """Search for username across all platforms"""
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"Searching for username: {username}\n", "header")
        self.results_text.insert(tk.END, "=" * 60 + "\n\n")
        
        found_count = 0
        total_platforms = len(self.platforms)
        
        for idx, (platform, url_template) in enumerate(self.platforms.items(), 1):
            if not self.is_searching:
                break
                
            self.update_status(f"Checking {platform}... ({idx}/{total_platforms})")
            
            status, url = self.check_username(platform, url_template, username)
            
            # Update results
            platform_text = f"[{platform}] "
            self.results_text.insert(tk.END, platform_text)
            
            if status == 'found':
                self.results_text.insert(tk.END, "✓ FOUND\n", "found")
                self.results_text.insert(tk.END, f"  → {url}\n\n", "link")
                found_count += 1
            elif status == 'notfound':
                self.results_text.insert(tk.END, "✗ Not found\n\n", "notfound")
            else:
                self.results_text.insert(tk.END, "? Unable to verify\n\n", "error")
            
            self.results_text.see(tk.END)
            self.root.update_idletasks()
            
            # Small delay to avoid rate limiting
            time.sleep(0.3)
        
        # Summary
        self.results_text.insert(tk.END, "\n" + "=" * 60 + "\n")
        summary = f"Search complete! Found on {found_count} out of {total_platforms} platforms.\n"
        self.results_text.insert(tk.END, summary, "header")
        
        self.update_status(f"Complete - Found on {found_count} platforms")
        self.progress.stop()
        self.search_button.config(state='normal', text='Search')
        self.is_searching = False
        
    def start_search(self):
        username = self.username_entry.get().strip()
        
        if not username:
            self.update_status("Please enter a username")
            return
            
        if self.is_searching:
            self.is_searching = False
            self.search_button.config(text='Search')
            self.progress.stop()
            self.update_status("Search cancelled")
            return
            
        self.is_searching = True
        self.search_button.config(text='Cancel')
        self.progress.start(10)
        
        # Run search in separate thread
        search_thread = threading.Thread(target=self.search_platforms, args=(username,))
        search_thread.daemon = True
        search_thread.start()

def main():
    root = tk.Tk()
    app = UsernameFinder(root)
    root.mainloop()

if __name__ == "__main__":
    main()
