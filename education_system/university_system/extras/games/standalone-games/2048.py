import tkinter as tk
from tkinter import messagebox
import random
import copy

class Game2048:
    def __init__(self, root):
        self.root = root
        self.root.title("2048 Game")
        self.root.resizable(False, False)
        
        # Game configuration
        self.grid_size = 4
        self.cell_size = 100
        self.cell_padding = 10
        
        # Color scheme
        self.bg_color = "#bbada0"
        self.empty_cell_color = "#cdc1b4"
        self.colors = {
            0: "#cdc1b4",
            2: "#eee4da",
            4: "#ede0c8",
            8: "#f2b179",
            16: "#f59563",
            32: "#f67c5f",
            64: "#f65e3b",
            128: "#edcf72",
            256: "#edcc61",
            512: "#edc850",
            1024: "#edc53f",
            2048: "#edc22e",
        }
        self.text_colors = {
            2: "#776e65",
            4: "#776e65",
        }
        
        # Initialize game state
        self.grid = [[0] * self.grid_size for _ in range(self.grid_size)]
        self.score = 0
        
        # Create UI
        self.create_widgets()
        self.start_game()
        
        # Bind keyboard events
        self.root.bind("<Key>", self.key_press)
        
    def create_widgets(self):
        # Header frame
        header_frame = tk.Frame(self.root, bg="#faf8ef")
        header_frame.pack(pady=10)
        
        # Title
        title_label = tk.Label(
            header_frame,
            text="2048",
            font=("Helvetica", 40, "bold"),
            bg="#faf8ef",
            fg="#776e65"
        )
        title_label.pack(side=tk.LEFT, padx=20)
        
        # Score frame
        score_frame = tk.Frame(header_frame, bg="#bbada0", padx=15, pady=10)
        score_frame.pack(side=tk.LEFT, padx=10)
        
        tk.Label(
            score_frame,
            text="SCORE",
            font=("Helvetica", 10, "bold"),
            bg="#bbada0",
            fg="#eee4da"
        ).pack()
        
        self.score_label = tk.Label(
            score_frame,
            text="0",
            font=("Helvetica", 22, "bold"),
            bg="#bbada0",
            fg="white"
        )
        self.score_label.pack()
        
        # New game button
        new_game_btn = tk.Button(
            header_frame,
            text="New Game",
            font=("Helvetica", 12, "bold"),
            bg="#8f7a66",
            fg="white",
            padx=15,
            pady=10,
            command=self.start_game,
            relief=tk.FLAT,
            cursor="hand2"
        )
        new_game_btn.pack(side=tk.LEFT, padx=10)
        
        # Game canvas
        canvas_size = self.grid_size * self.cell_size + (self.grid_size + 1) * self.cell_padding
        self.canvas = tk.Canvas(
            self.root,
            width=canvas_size,
            height=canvas_size,
            bg=self.bg_color,
            highlightthickness=0
        )
        self.canvas.pack(pady=10)
        
        # Instructions
        instructions = tk.Label(
            self.root,
            text="Use arrow keys to play",
            font=("Helvetica", 10),
            bg="#faf8ef",
            fg="#776e65"
        )
        instructions.pack(pady=5)
        
    def start_game(self):
        self.grid = [[0] * self.grid_size for _ in range(self.grid_size)]
        self.score = 0
        self.update_score()
        self.add_new_tile()
        self.add_new_tile()
        self.draw_grid()
        
    def add_new_tile(self):
        empty_cells = [(i, j) for i in range(self.grid_size) 
                       for j in range(self.grid_size) if self.grid[i][j] == 0]
        if empty_cells:
            i, j = random.choice(empty_cells)
            self.grid[i][j] = 2 if random.random() < 0.9 else 4
            
    def draw_grid(self):
        self.canvas.delete("all")
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                x = j * self.cell_size + (j + 1) * self.cell_padding
                y = i * self.cell_size + (i + 1) * self.cell_padding
                
                value = self.grid[i][j]
                color = self.colors.get(value, "#3c3a32")
                
                # Draw cell
                self.canvas.create_rectangle(
                    x, y,
                    x + self.cell_size,
                    y + self.cell_size,
                    fill=color,
                    outline=""
                )
                
                # Draw number
                if value != 0:
                    text_color = self.text_colors.get(value, "#f9f6f2")
                    font_size = 40 if value < 100 else (35 if value < 1000 else 30)
                    
                    self.canvas.create_text(
                        x + self.cell_size / 2,
                        y + self.cell_size / 2,
                        text=str(value),
                        font=("Helvetica", font_size, "bold"),
                        fill=text_color
                    )
    
    def update_score(self):
        self.score_label.config(text=str(self.score))
    
    def key_press(self, event):
        key = event.keysym
        moved = False
        
        if key == "Up":
            moved = self.move_up()
        elif key == "Down":
            moved = self.move_down()
        elif key == "Left":
            moved = self.move_left()
        elif key == "Right":
            moved = self.move_right()
        
        if moved:
            self.add_new_tile()
            self.draw_grid()
            
            if self.is_game_over():
                messagebox.showinfo("Game Over", f"Game Over!\nYour score: {self.score}")
            elif self.has_won():
                response = messagebox.askyesno(
                    "You Won!",
                    f"Congratulations! You've reached 2048!\nScore: {self.score}\n\nContinue playing?"
                )
                if not response:
                    self.start_game()
    
    def compress(self, grid):
        new_grid = [[0] * self.grid_size for _ in range(self.grid_size)]
        for i in range(self.grid_size):
            pos = 0
            for j in range(self.grid_size):
                if grid[i][j] != 0:
                    new_grid[i][pos] = grid[i][j]
                    pos += 1
        return new_grid
    
    def merge(self, grid):
        for i in range(self.grid_size):
            for j in range(self.grid_size - 1):
                if grid[i][j] == grid[i][j + 1] and grid[i][j] != 0:
                    grid[i][j] *= 2
                    grid[i][j + 1] = 0
                    self.score += grid[i][j]
        return grid
    
    def reverse(self, grid):
        return [row[::-1] for row in grid]
    
    def transpose(self, grid):
        return [list(row) for row in zip(*grid)]
    
    def move_left(self):
        old_grid = copy.deepcopy(self.grid)
        self.grid = self.compress(self.grid)
        self.grid = self.merge(self.grid)
        self.grid = self.compress(self.grid)
        self.update_score()
        return old_grid != self.grid
    
    def move_right(self):
        old_grid = copy.deepcopy(self.grid)
        self.grid = self.reverse(self.grid)
        self.grid = self.compress(self.grid)
        self.grid = self.merge(self.grid)
        self.grid = self.compress(self.grid)
        self.grid = self.reverse(self.grid)
        self.update_score()
        return old_grid != self.grid
    
    def move_up(self):
        old_grid = copy.deepcopy(self.grid)
        self.grid = self.transpose(self.grid)
        self.grid = self.compress(self.grid)
        self.grid = self.merge(self.grid)
        self.grid = self.compress(self.grid)
        self.grid = self.transpose(self.grid)
        self.update_score()
        return old_grid != self.grid
    
    def move_down(self):
        old_grid = copy.deepcopy(self.grid)
        self.grid = self.transpose(self.grid)
        self.grid = self.reverse(self.grid)
        self.grid = self.compress(self.grid)
        self.grid = self.merge(self.grid)
        self.grid = self.compress(self.grid)
        self.grid = self.reverse(self.grid)
        self.grid = self.transpose(self.grid)
        self.update_score()
        return old_grid != self.grid
    
    def is_game_over(self):
        # Check for empty cells
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if self.grid[i][j] == 0:
                    return False
        
        # Check for possible merges
        for i in range(self.grid_size):
            for j in range(self.grid_size - 1):
                if self.grid[i][j] == self.grid[i][j + 1]:
                    return False
        
        for i in range(self.grid_size - 1):
            for j in range(self.grid_size):
                if self.grid[i][j] == self.grid[i + 1][j]:
                    return False
        
        return True
    
    def has_won(self):
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if self.grid[i][j] == 2048:
                    return True
        return False

def main():
    root = tk.Tk()
    root.configure(bg="#faf8ef")
    game = Game2048(root)
    root.mainloop()

if __name__ == "__main__":
    main()
