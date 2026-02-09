import tkinter as tk
from tkinter import messagebox
import random

class HangmanGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Hangman Game")
        self.root.geometry("600x700")
        self.root.resizable(False, False)
        self.root.configure(bg="#2C3E50")
        
        # Word list
        self.word_list = [
            "python", "programming", "computer", "keyboard", "software",
            "algorithm", "variable", "function", "database", "network",
            "interface", "developer", "application", "framework", "library"
        ]
        
        # Game variables
        self.word = ""
        self.guessed_letters = set()
        self.remaining_tries = 6
        self.game_over = False
        
        self.setup_ui()
        self.new_game()
        
    def setup_ui(self):
        # Title
        title_label = tk.Label(
            self.root,
            text="🎮 HANGMAN GAME 🎮",
            font=("Arial", 28, "bold"),
            bg="#2C3E50",
            fg="#ECF0F1"
        )
        title_label.pack(pady=20)
        
        # Canvas for hangman drawing
        self.canvas = tk.Canvas(
            self.root,
            width=300,
            height=300,
            bg="#ECF0F1",
            highlightthickness=2,
            highlightbackground="#34495E"
        )
        self.canvas.pack(pady=10)
        
        # Draw gallows
        self.draw_gallows()
        
        # Tries remaining label
        self.tries_label = tk.Label(
            self.root,
            text=f"Tries Remaining: {self.remaining_tries}",
            font=("Arial", 16, "bold"),
            bg="#2C3E50",
            fg="#E74C3C"
        )
        self.tries_label.pack(pady=10)
        
        # Word display
        self.word_label = tk.Label(
            self.root,
            text="",
            font=("Courier", 32, "bold"),
            bg="#2C3E50",
            fg="#3498DB"
        )
        self.word_label.pack(pady=20)
        
        # Guessed letters display
        self.guessed_label = tk.Label(
            self.root,
            text="Guessed: ",
            font=("Arial", 12),
            bg="#2C3E50",
            fg="#95A5A6"
        )
        self.guessed_label.pack(pady=5)
        
        # Letter buttons frame
        self.buttons_frame = tk.Frame(self.root, bg="#2C3E50")
        self.buttons_frame.pack(pady=20)
        
        # Create letter buttons
        self.letter_buttons = {}
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        for i, letter in enumerate(letters):
            row = i // 9
            col = i % 9
            
            btn = tk.Button(
                self.buttons_frame,
                text=letter,
                font=("Arial", 12, "bold"),
                width=3,
                height=1,
                bg="#3498DB",
                fg="white",
                activebackground="#2980B9",
                command=lambda l=letter: self.guess_letter(l)
            )
            btn.grid(row=row, column=col, padx=3, pady=3)
            self.letter_buttons[letter] = btn
        
        # New game button
        self.new_game_btn = tk.Button(
            self.root,
            text="New Game",
            font=("Arial", 14, "bold"),
            bg="#27AE60",
            fg="white",
            activebackground="#229954",
            command=self.new_game,
            width=15,
            height=2
        )
        self.new_game_btn.pack(pady=10)
        
    def draw_gallows(self):
        """Draw the gallows base"""
        self.canvas.delete("all")
        # Base
        self.canvas.create_line(50, 280, 250, 280, width=4, fill="#34495E")
        # Vertical pole
        self.canvas.create_line(100, 280, 100, 50, width=4, fill="#34495E")
        # Horizontal pole
        self.canvas.create_line(100, 50, 200, 50, width=4, fill="#34495E")
        # Rope
        self.canvas.create_line(200, 50, 200, 80, width=3, fill="#34495E")
        
    def draw_hangman(self, tries_left):
        """Draw hangman parts based on remaining tries"""
        if tries_left == 5:  # Head
            self.canvas.create_oval(175, 80, 225, 130, width=3, outline="#E74C3C")
        elif tries_left == 4:  # Body
            self.canvas.create_line(200, 130, 200, 200, width=3, fill="#E74C3C")
        elif tries_left == 3:  # Left arm
            self.canvas.create_line(200, 150, 170, 170, width=3, fill="#E74C3C")
        elif tries_left == 2:  # Right arm
            self.canvas.create_line(200, 150, 230, 170, width=3, fill="#E74C3C")
        elif tries_left == 1:  # Left leg
            self.canvas.create_line(200, 200, 175, 240, width=3, fill="#E74C3C")
        elif tries_left == 0:  # Right leg
            self.canvas.create_line(200, 200, 225, 240, width=3, fill="#E74C3C")
            
    def new_game(self):
        """Start a new game"""
        self.word = random.choice(self.word_list).upper()
        self.guessed_letters = set()
        self.remaining_tries = 6
        self.game_over = False
        
        # Reset UI
        self.draw_gallows()
        self.update_word_display()
        self.tries_label.config(text=f"Tries Remaining: {self.remaining_tries}")
        self.guessed_label.config(text="Guessed: ")
        
        # Enable all buttons
        for btn in self.letter_buttons.values():
            btn.config(state="normal", bg="#3498DB")
            
    def update_word_display(self):
        """Update the word display with guessed letters"""
        display = ""
        for letter in self.word:
            if letter in self.guessed_letters:
                display += letter + " "
            else:
                display += "_ "
        self.word_label.config(text=display.strip())
        
    def guess_letter(self, letter):
        """Handle a letter guess"""
        if self.game_over:
            return
            
        # Disable the button
        self.letter_buttons[letter].config(state="disabled", bg="#7F8C8D")
        
        # Add to guessed letters
        self.guessed_letters.add(letter)
        
        # Update guessed letters display
        guessed_str = ", ".join(sorted(self.guessed_letters))
        self.guessed_label.config(text=f"Guessed: {guessed_str}")
        
        # Check if letter is in word
        if letter not in self.word:
            self.remaining_tries -= 1
            self.tries_label.config(text=f"Tries Remaining: {self.remaining_tries}")
            self.draw_hangman(self.remaining_tries)
            
            # Check for loss
            if self.remaining_tries == 0:
                self.game_over = True
                self.word_label.config(text=self.word)
                messagebox.showinfo(
                    "Game Over",
                    f"You lost! The word was: {self.word}\n\nClick 'New Game' to play again."
                )
                # Disable all buttons
                for btn in self.letter_buttons.values():
                    btn.config(state="disabled")
        else:
            self.update_word_display()
            
            # Check for win
            if all(letter in self.guessed_letters for letter in self.word):
                self.game_over = True
                messagebox.showinfo(
                    "Congratulations!",
                    f"You won! The word was: {self.word}\n\nClick 'New Game' to play again."
                )
                # Disable all buttons
                for btn in self.letter_buttons.values():
                    btn.config(state="disabled")

def main():
    root = tk.Tk()
    game = HangmanGame(root)
    root.mainloop()

if __name__ == "__main__":
    main()
