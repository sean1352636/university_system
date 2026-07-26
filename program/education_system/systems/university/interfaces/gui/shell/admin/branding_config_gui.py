"""Institution Branding & Customization GUI.

Configure institution name/logo/colors, customize email templates,
system message customization, and UI theme selection.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import logging
import json
import shutil
from datetime import datetime
from pathlib import Path

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.paths import BRANDING_DIR

logger = logging.getLogger(__name__)

# Default branding settings
DEFAULT_BRANDING = {
    'institution_name': 'Teesside University',
    'institution_abbreviation': 'TU',
    'tagline': 'University Management System',
    'primary_color': '#2C3E50',
    'secondary_color': '#3498DB',
    'accent_color': '#E74C3C',
    'logo_path': '',
    'email_signature': '\n\nRegards,\nTeesside University',
    'system_welcome_message': 'Welcome to the University Management System',
    'footer_text': 'University Management System v5.17.0',
}


def get_branding_setting(key):
    """Return a single branding setting, falling back to its default.

    Reads the same ``security_settings`` rows the config GUI writes, so
    callers outside this module (e.g. the dashboard welcome banner) stay in
    step with whatever an admin last saved.
    """
    default = DEFAULT_BRANDING.get(key, '')
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT setting_value FROM security_settings WHERE setting_name = ?",
                (f"branding_{key}",)
            ).fetchone()
        if row and row['setting_value']:
            return row['setting_value']
    except Exception as e:
        logger.debug(f"Could not read branding setting {key}: {e}")
    return default


def get_institution_display_name():
    """Institution name suffixed with "University" unless it already says so.

    The configured name is commonly already qualified (the default is
    "Teesside University"), so blindly appending would read "… University
    University".
    """
    name = (get_branding_setting('institution_name') or '').strip()
    if not name:
        name = DEFAULT_BRANDING['institution_name']
    if 'university' in name.lower():
        return name
    return f"{name} University"


def get_logo_path():
    """Absolute :class:`Path` to the configured logo, or ``None``.

    Returns ``None`` when nothing is configured or the file has since been
    moved or deleted, so callers can simply fall back to text.
    """
    raw = (get_branding_setting('logo_path') or '').strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = BRANDING_DIR / p
    return p if p.is_file() else None


def _load_image(path, max_height=48):
    """Load *path* as a Tk-displayable image scaled to *max_height*.

    Prefers Pillow (handles JPEG and gives clean downscaling) and falls back
    to ``tk.PhotoImage``, which covers PNG/GIF on Tk 8.6. Returns ``None`` if
    the file is missing or cannot be decoded.
    """
    if not path:
        return None
    path = Path(path)
    if not path.is_absolute():
        path = BRANDING_DIR / path
    if not path.is_file():
        return None
    try:
        from PIL import Image, ImageTk
        img = Image.open(path)
        if img.height > max_height:
            ratio = max_height / img.height
            img = img.resize((max(1, int(img.width * ratio)), max_height), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Could not load logo {path}: {e}")
        return None
    try:
        img = tk.PhotoImage(file=str(path))
        if img.height() > max_height:
            img = img.subsample(max(1, img.height() // max_height))
        return img
    except Exception as e:
        logger.warning(f"Could not load logo {path} without Pillow: {e}")
        return None


def load_logo_image(max_height=48):
    """The configured institution logo as a Tk image, or ``None``.

    Callers must keep a reference to the returned image or Tk will garbage
    collect it and render a blank label.
    """
    return _load_image(get_logo_path(), max_height=max_height)


class BrandingConfigGUI(tk.Toplevel):
    """Admin GUI for institution branding and customization."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Institution Branding & Customization")
        self.geometry("900x650")
        self.transient(parent)

        self.settings = dict(DEFAULT_BRANDING)
        self._load_settings()
        self._create_widgets()

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _load_settings(self):
        """Load branding settings from the database."""
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT setting_name, setting_value FROM security_settings "
                    "WHERE setting_name LIKE 'branding_%'"
                ).fetchall()
                for r in rows:
                    key = r['setting_name'].replace('branding_', '', 1)
                    if key in self.settings:
                        self.settings[key] = r['setting_value']
        except Exception as e:
            logger.debug(f"Could not load branding settings: {e}")

    def _save_settings(self):
        """Save branding settings to the database."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with transaction() as conn:
                for key, value in self.settings.items():
                    setting_name = f"branding_{key}"
                    existing = conn.execute(
                        "SELECT id FROM security_settings WHERE setting_name = ?",
                        (setting_name,)
                    ).fetchone()
                    if existing:
                        conn.execute(
                            "UPDATE security_settings SET setting_value = ?, "
                            "updated_at = ? WHERE setting_name = ?",
                            (str(value), now, setting_name)
                        )
                    else:
                        conn.execute(
                            "INSERT INTO security_settings "
                            "(setting_name, setting_value, updated_at, updated_by) "
                            "VALUES (?, ?, ?, 'admin')",
                            (setting_name, str(value), now)
                        )
            messagebox.showinfo("Saved", "Branding settings saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def _create_widgets(self):
        # Header
        header = tk.Frame(self, bg="#8E24AA", height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Institution Branding & Customization",
                 font=("Arial", 14, "bold"), bg="#8E24AA", fg="white").pack(pady=12)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_identity_tab()
        self._create_colors_tab()
        self._create_messages_tab()
        self._create_theme_tab()
        self._create_templates_tab()

        # Save button at bottom
        save_frame = ttk.Frame(self)
        save_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(save_frame, text="Save All Settings",
                   command=self._save_all).pack(side=tk.RIGHT, padx=5)
        ttk.Button(save_frame, text="Reset to Defaults",
                   command=self._reset_defaults).pack(side=tk.RIGHT, padx=5)

    # ------------------------------------------------------------------
    # Institution Identity Tab
    # ------------------------------------------------------------------
    def _create_identity_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Identity")

        container = ttk.Frame(tab, padding="20")
        container.pack(fill=tk.BOTH, expand=True)

        self.identity_entries = {}
        fields = [
            ("Institution Name:", "institution_name"),
            ("Abbreviation:", "institution_abbreviation"),
            ("Tagline:", "tagline"),
            ("Logo Path:", "logo_path"),
        ]

        for i, (label, key) in enumerate(fields):
            ttk.Label(container, text=label, font=('Arial', 10)).grid(
                row=i, column=0, sticky="w", pady=8)
            e = ttk.Entry(container, width=50)
            e.insert(0, self.settings.get(key, ''))
            e.grid(row=i, column=1, padx=10, pady=8, sticky="ew")
            self.identity_entries[key] = e

        # Logo browse button
        ttk.Button(container, text="Browse...",
                   command=self._browse_logo).grid(row=3, column=2, padx=5)

        # Tell the admin where the file actually ends up — browsing copies it
        # here, and dropping a file in by hand works just as well.
        ttk.Label(container,
                  text=f"Logos are stored in:  {BRANDING_DIR}",
                  font=('Arial', 8), foreground='#666666').grid(
            row=4, column=1, columnspan=2, sticky="w", padx=10)

        container.columnconfigure(1, weight=1)

        # Preview
        preview_frame = ttk.LabelFrame(container, text="Preview", padding="15")
        preview_frame.grid(row=len(fields) + 1, column=0, columnspan=3,
                           sticky="ew", pady=15)

        # Kept on self so Tk does not garbage-collect the image.
        self._logo_preview_image = None
        self.preview_logo = ttk.Label(preview_frame)
        self.preview_logo.pack()
        self.preview_label = ttk.Label(preview_frame, text="", font=('Arial', 14, 'bold'))
        self.preview_label.pack()
        self.preview_tagline = ttk.Label(preview_frame, text="", font=('Arial', 10, 'italic'))
        self.preview_tagline.pack()
        self._update_identity_preview()

        ttk.Button(container, text="Update Preview",
                   command=self._update_identity_preview).grid(
            row=len(fields) + 2, column=1, pady=5)

    def _browse_logo(self):
        path = filedialog.askopenfilename(
            title="Select Logo Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All", "*.*")]
        )
        if not path:
            return
        # Copy into the branding directory rather than referencing wherever
        # the admin happened to browse from — a path under /home or a USB
        # stick would break for every other user and on the next machine.
        stored = path
        try:
            BRANDING_DIR.mkdir(parents=True, exist_ok=True)
            dest = BRANDING_DIR / f"logo{Path(path).suffix.lower()}"
            if Path(path).resolve() != dest.resolve():
                shutil.copyfile(path, dest)
            stored = str(dest)
        except OSError as e:
            logger.warning(f"Could not copy logo into {BRANDING_DIR}: {e}")
            messagebox.showwarning(
                "Logo",
                f"Could not copy the logo into the branding folder:\n{e}\n\n"
                "The original path will be used instead, which may not resolve "
                "on another machine."
            )
        self.identity_entries['logo_path'].delete(0, tk.END)
        self.identity_entries['logo_path'].insert(0, stored)
        # Persist immediately so the preview (which reads from the DB) shows
        # the new file rather than the previously saved one.
        self.settings['logo_path'] = stored
        self._save_settings()
        self._update_identity_preview()

    def _update_identity_preview(self):
        name = self.identity_entries.get('institution_name')
        tagline = self.identity_entries.get('tagline')
        self.preview_label.config(
            text=name.get() if name else self.settings['institution_name'])
        self.preview_tagline.config(
            text=tagline.get() if tagline else self.settings['tagline'])

        entry = self.identity_entries.get('logo_path')
        raw = entry.get().strip() if entry else ''
        self._logo_preview_image = _load_image(raw, max_height=96) if raw else None
        if self._logo_preview_image is not None:
            self.preview_logo.config(image=self._logo_preview_image, text='')
        else:
            self.preview_logo.config(
                image='',
                text="(no logo set)" if not raw else "(logo could not be loaded)")

    # ------------------------------------------------------------------
    # Colors Tab
    # ------------------------------------------------------------------
    def _create_colors_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Colors")

        container = ttk.Frame(tab, padding="20")
        container.pack(fill=tk.BOTH, expand=True)

        self.color_entries = {}
        self.color_swatches = {}

        color_fields = [
            ("Primary Color:", "primary_color"),
            ("Secondary Color:", "secondary_color"),
            ("Accent Color:", "accent_color"),
        ]

        for i, (label, key) in enumerate(color_fields):
            ttk.Label(container, text=label, font=('Arial', 10)).grid(
                row=i, column=0, sticky="w", pady=8)

            e = ttk.Entry(container, width=20)
            e.insert(0, self.settings.get(key, '#000000'))
            e.grid(row=i, column=1, padx=10, pady=8)
            self.color_entries[key] = e

            swatch = tk.Frame(container, width=40, height=25,
                              bg=self.settings.get(key, '#000000'),
                              relief="solid", borderwidth=1)
            swatch.grid(row=i, column=2, padx=5, pady=8)
            self.color_swatches[key] = swatch

            ttk.Button(container, text="Pick",
                       command=lambda k=key: self._pick_color(k)).grid(
                row=i, column=3, padx=5, pady=8)

        # Color preview
        preview = ttk.LabelFrame(container, text="Color Preview", padding="15")
        preview.grid(row=len(color_fields), column=0, columnspan=4,
                     sticky="ew", pady=15)

        self.color_preview_frame = tk.Frame(preview, height=60)
        self.color_preview_frame.pack(fill=tk.X)
        self._update_color_preview()

    def _pick_color(self, key):
        current = self.color_entries[key].get()
        result = colorchooser.askcolor(color=current, title=f"Choose {key}")
        if result and result[1]:
            self.color_entries[key].delete(0, tk.END)
            self.color_entries[key].insert(0, result[1])
            self.color_swatches[key].config(bg=result[1])
            self._update_color_preview()

    def _update_color_preview(self):
        for w in self.color_preview_frame.winfo_children():
            w.destroy()

        primary = self.color_entries.get('primary_color')
        secondary = self.color_entries.get('secondary_color')
        accent = self.color_entries.get('accent_color')

        colors = [
            ("Primary", primary.get() if primary else '#2C3E50'),
            ("Secondary", secondary.get() if secondary else '#3498DB'),
            ("Accent", accent.get() if accent else '#E74C3C'),
        ]

        for i, (label, color) in enumerate(colors):
            try:
                f = tk.Frame(self.color_preview_frame, bg=color, width=150, height=50)
                f.pack(side=tk.LEFT, padx=10, pady=5, expand=True, fill=tk.X)
                f.pack_propagate(False)
                tk.Label(f, text=label, fg="white", bg=color,
                         font=('Arial', 10, 'bold')).pack(expand=True)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------
    # System Messages Tab
    # ------------------------------------------------------------------
    def _create_messages_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Messages")

        container = ttk.Frame(tab, padding="20")
        container.pack(fill=tk.BOTH, expand=True)

        self.message_entries = {}

        # Welcome message
        ttk.Label(container, text="System Welcome Message:",
                  font=('Arial', 10)).pack(anchor="w")
        welcome = ttk.Entry(container, width=70)
        welcome.insert(0, self.settings.get('system_welcome_message', ''))
        welcome.pack(fill=tk.X, pady=(0, 15))
        self.message_entries['system_welcome_message'] = welcome

        # Footer text
        ttk.Label(container, text="Footer Text:",
                  font=('Arial', 10)).pack(anchor="w")
        footer = ttk.Entry(container, width=70)
        footer.insert(0, self.settings.get('footer_text', ''))
        footer.pack(fill=tk.X, pady=(0, 15))
        self.message_entries['footer_text'] = footer

        # Email signature
        ttk.Label(container, text="Email Signature:",
                  font=('Arial', 10)).pack(anchor="w")
        sig = tk.Text(container, height=6, width=70)
        sig.insert('1.0', self.settings.get('email_signature', ''))
        sig.pack(fill=tk.X, pady=(0, 15))
        self.message_entries['email_signature'] = sig

    # ------------------------------------------------------------------
    # Theme Tab
    # ------------------------------------------------------------------
    def _create_theme_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="UI Theme")

        container = ttk.Frame(tab, padding="20")
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="UI Theme Selection",
                  font=('Arial', 13, 'bold')).pack(anchor="w", pady=(0, 15))

        self.theme_var = tk.StringVar(value="light")

        # Try to read current theme
        try:
            from education_system.systems.university.interfaces.gui.shell.theme_config import ThemeManager
            tm = ThemeManager()
            if tm._dark_mode:
                self.theme_var.set("dark")
        except Exception:
            pass

        themes = ttk.LabelFrame(container, text="Select Theme", padding="15")
        themes.pack(fill=tk.X, pady=5)

        ttk.Radiobutton(themes, text="Light Mode",
                        variable=self.theme_var, value="light").pack(anchor="w", pady=3)
        ttk.Radiobutton(themes, text="Dark Mode",
                        variable=self.theme_var, value="dark").pack(anchor="w", pady=3)

        ttk.Button(container, text="Apply Theme",
                   command=self._apply_theme).pack(anchor="w", pady=15)

        # Info
        info = ttk.LabelFrame(container, text="Theme Info", padding="15")
        info.pack(fill=tk.X, pady=5)
        ttk.Label(info, text="Theme changes will apply to newly opened windows.\n"
                  "The main application may need to be restarted for full effect.",
                  wraplength=400).pack(anchor="w")

    def _apply_theme(self):
        try:
            from education_system.systems.university.interfaces.gui.shell.theme_config import ThemeManager
            tm = ThemeManager()
            dark = self.theme_var.get() == "dark"
            tm.set_dark_mode(dark)
            messagebox.showinfo("Theme Applied",
                                f"{'Dark' if dark else 'Light'} mode activated.\n"
                                "New windows will use the selected theme.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not apply theme: {e}")

    # ------------------------------------------------------------------
    # Email Templates Tab
    # ------------------------------------------------------------------
    def _create_templates_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Email Templates")

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Refresh",
                   command=self._load_email_templates).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit Selected",
                   command=self._edit_email_template).pack(side=tk.LEFT, padx=5)

        cols = ("name", "category", "subject")
        self.email_templates_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                                  height=15)
        self.email_templates_tree.heading("name", text="Template Name")
        self.email_templates_tree.heading("category", text="Category")
        self.email_templates_tree.heading("subject", text="Subject")
        self.email_templates_tree.column("name", width=250)
        self.email_templates_tree.column("category", width=150)
        self.email_templates_tree.column("subject", width=350)

        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL,
                               command=self.email_templates_tree.yview)
        self.email_templates_tree.configure(yscrollcommand=scroll.set)
        self.email_templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                                        padx=(10, 0), pady=5)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)

        self._load_email_templates()

    def _load_email_templates(self):
        for item in self.email_templates_tree.get_children():
            self.email_templates_tree.delete(item)
        try:
            from education_system.systems.university.infrastructure.email.template_utils import list_templates
            templates = list_templates()
            for t in templates:
                self.email_templates_tree.insert('', tk.END, values=(
                    t.get('name', ''),
                    t.get('category', ''),
                    t.get('subject', ''),
                ))
        except Exception as e:
            logger.debug(f"Could not load email templates: {e}")

    def _edit_email_template(self):
        sel = self.email_templates_tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a template first.")
            return
        template_name = self.email_templates_tree.item(sel[0])['values'][0]

        try:
            from education_system.systems.university.infrastructure.email.template_utils import (
                load_template, update_template
            )
            data = load_template(template_name)
            if not data:
                messagebox.showerror("Error", "Could not load template.")
                return

            dialog = tk.Toplevel(self)
            dialog.title(f"Edit: {template_name}")
            dialog.geometry("550x450")
            dialog.transient(self)
            dialog.grab_set()

            ttk.Label(dialog, text="Subject:").pack(anchor="w", padx=10, pady=(10, 0))
            subject_entry = ttk.Entry(dialog, width=60)
            subject_entry.insert(0, data.get('subject', ''))
            subject_entry.pack(fill=tk.X, padx=10, pady=5)

            ttk.Label(dialog, text="Body:").pack(anchor="w", padx=10)
            body_text = tk.Text(dialog, height=15, width=60)
            body_text.insert('1.0', data.get('body', ''))
            body_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            def save():
                try:
                    update_template(
                        template_name,
                        subject=subject_entry.get().strip(),
                        body=body_text.get('1.0', tk.END).strip()
                    )
                    dialog.destroy()
                    self._load_email_templates()
                    messagebox.showinfo("Saved", f"Template '{template_name}' updated.")
                except Exception as e:
                    messagebox.showerror("Error", str(e))

            ttk.Button(dialog, text="Save", command=save).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Could not edit template: {e}")

    # ------------------------------------------------------------------
    # Save / Reset
    # ------------------------------------------------------------------
    def _save_all(self):
        """Collect all values from UI and save."""
        # Identity
        for key, entry in self.identity_entries.items():
            self.settings[key] = entry.get().strip()

        # Colors
        for key, entry in self.color_entries.items():
            self.settings[key] = entry.get().strip()

        # Messages
        for key, entry in self.message_entries.items():
            if isinstance(entry, tk.Text):
                self.settings[key] = entry.get('1.0', tk.END).strip()
            else:
                self.settings[key] = entry.get().strip()

        self._save_settings()

    def _reset_defaults(self):
        if messagebox.askyesno("Reset", "Reset all branding settings to defaults?"):
            self.settings = dict(DEFAULT_BRANDING)
            self._save_settings()
            self.destroy()
