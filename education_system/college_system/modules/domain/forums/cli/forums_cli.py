"""Discussion Forums CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.forums.services.forums_service import ForumService
from education_system.college_system.infrastructure.auth.core import UserAuth


def forums_menu(auth: UserAuth):
    """Discussion Forums management menu."""
    svc = ForumService(auth._db_path)
    user_id = auth.current_user["user_id"]

    while True:
        print_header("Discussion Forums")
        options = [
            ("1", "List Categories"),
            ("2", "Create Category"),
            ("3", "Edit Category"),
            ("4", "Delete Category"),
            ("5", "List Threads"),
            ("6", "Create Thread"),
            ("7", "View Thread & Posts"),
            ("8", "Edit Thread"),
            ("9", "Pin/Unpin Thread"),
            ("10", "Lock/Unlock Thread"),
            ("11", "Delete Thread"),
            ("12", "Create Post"),
            ("13", "Edit Post"),
            ("14", "Delete Post"),
            ("15", "Mark Post as Solution"),
            ("16", "Forum Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _list_categories(svc)
        elif choice == "2":
            _create_category(svc)
        elif choice == "3":
            _edit_category(svc)
        elif choice == "4":
            _delete_category(svc)
        elif choice == "5":
            _list_threads(svc)
        elif choice == "6":
            _create_thread(svc, user_id)
        elif choice == "7":
            _view_thread(svc)
        elif choice == "8":
            _edit_thread(svc)
        elif choice == "9":
            _pin_thread(svc)
        elif choice == "10":
            _lock_thread(svc)
        elif choice == "11":
            _delete_thread(svc)
        elif choice == "12":
            _create_post(svc, user_id)
        elif choice == "13":
            _edit_post(svc)
        elif choice == "14":
            _delete_post(svc)
        elif choice == "15":
            _mark_solution(svc)
        elif choice == "16":
            _forum_stats(svc)
        else:
            print("\n  Invalid option.")


# ── Categories ──────────────────────────────────────────────────────────


def _list_categories(svc):
    cats = svc.list_categories()
    if not cats:
        print("\n  No categories found.")
        return
    print(f"\n  {'ID':<5} {'Name':<25} {'Description':<35} {'Order':<6} {'Active'}")
    print(f"  {'-' * 80}")
    for c in cats:
        desc = (c.get("description") or "")[:33]
        active = "Yes" if c.get("is_active", 1) else "No"
        print(f"  {c['id']:<5} {c['name'][:23]:<25} {desc:<35} "
              f"{c.get('sort_order', 0):<6} {active}")


def _create_category(svc):
    print_header("Create Category")
    name = input("  Name: ").strip()
    if not name:
        print("\n  Name is required.")
        return
    description = input("  Description: ").strip()
    order = input("  Sort order [0]: ").strip() or "0"
    try:
        cat = svc.create_category(name, description, int(order))
        print(f"\n  Category created (ID: {cat['id']})")
    except Exception as e:
        print(f"\n  Error: {e}")


def _edit_category(svc):
    cat_id = input("  Category ID: ").strip()
    if not cat_id:
        return
    cat = svc.get_category(int(cat_id))
    if not cat:
        print("\n  Category not found.")
        return
    print(f"  Current name: {cat['name']}")
    name = input("  New name (Enter to keep): ").strip() or cat["name"]
    description = input("  New description (Enter to keep): ").strip() or cat.get("description", "")
    order = input(f"  Sort order [{cat.get('sort_order', 0)}]: ").strip()
    order = int(order) if order else cat.get("sort_order", 0)
    try:
        svc.update_category(int(cat_id), name=name, description=description,
                            sort_order=order)
        print("\n  Category updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_category(svc):
    cat_id = input("  Category ID to delete: ").strip()
    if not cat_id:
        return
    confirm = input("  Are you sure? (y/n): ").strip().lower()
    if confirm != "y":
        print("\n  Cancelled.")
        return
    try:
        svc.delete_category(int(cat_id))
        print("\n  Category deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Threads ─────────────────────────────────────────────────────────────


def _list_threads(svc):
    cat_id = input("  Filter by category ID (Enter for all): ").strip()
    cat_id = int(cat_id) if cat_id else None
    search = input("  Search title (Enter to skip): ").strip() or None
    threads = svc.list_threads(category_id=cat_id, search=search)
    if not threads:
        print("\n  No threads found.")
        return
    print(f"\n  {'ID':<5} {'Title':<30} {'Author':<12} {'Replies':<8} "
          f"{'Status':<8} {'Pin':<4} {'Lock'}")
    print(f"  {'-' * 80}")
    for t in threads:
        pin = "Y" if t.get("is_pinned") else ""
        lock = "Y" if t.get("is_locked") else ""
        print(f"  {t['id']:<5} {t['title'][:28]:<30} "
              f"{t.get('author_name', '')[:10]:<12} "
              f"{t.get('reply_count', 0):<8} {t.get('status', 'open'):<8} "
              f"{pin:<4} {lock}")


def _create_thread(svc, user_id):
    print_header("Create Thread")
    _list_categories(svc)
    cat_id = input("\n  Category ID: ").strip()
    if not cat_id:
        return
    title = input("  Title: ").strip()
    if not title:
        print("\n  Title is required.")
        return
    try:
        thread = svc.create_thread(int(cat_id), title, user_id)
        print(f"\n  Thread created (ID: {thread['id']})")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_thread(svc):
    thread_id = input("  Thread ID: ").strip()
    if not thread_id:
        return
    try:
        thread = svc.get_thread(int(thread_id))
    except Exception as e:
        print(f"\n  Error: {e}")
        return
    if not thread:
        print("\n  Thread not found.")
        return

    pin = " [PINNED]" if thread.get("is_pinned") else ""
    lock = " [LOCKED]" if thread.get("is_locked") else ""
    print(f"\n  Thread #{thread['id']} - {thread['title']}{pin}{lock}")
    print(f"  Category: {thread.get('category_name', 'N/A')} | "
          f"Author: {thread.get('author_name', 'N/A')} | "
          f"Status: {thread.get('status', 'open')}")
    print(f"  Views: {thread.get('view_count', 0)} | "
          f"Replies: {thread.get('reply_count', 0)}")

    posts = svc.list_posts(int(thread_id))
    if posts:
        print(f"\n  --- Posts ({len(posts)}) ---")
        for p in posts:
            sol = " [SOLUTION]" if p.get("is_solution") else ""
            edited = " (edited)" if p.get("edited_at") else ""
            print(f"  #{p['id']} [{p.get('author_name', '?')}]{sol}{edited}")
            print(f"    {p['content']}")
    else:
        print("\n  No posts yet.")


def _edit_thread(svc):
    thread_id = input("  Thread ID: ").strip()
    if not thread_id:
        return
    thread = svc.get_thread(int(thread_id))
    if not thread:
        print("\n  Thread not found.")
        return
    print(f"  Current title: {thread['title']}")
    title = input("  New title (Enter to keep): ").strip() or None
    status = input(f"  Status [{thread.get('status', 'open')}] "
                   f"(open/closed/resolved): ").strip() or None
    updates = {}
    if title:
        updates["title"] = title
    if status:
        updates["status"] = status
    if not updates:
        print("\n  No changes.")
        return
    try:
        svc.update_thread(int(thread_id), **updates)
        print("\n  Thread updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _pin_thread(svc):
    thread_id = input("  Thread ID: ").strip()
    if not thread_id:
        return
    thread = svc.get_thread(int(thread_id))
    if not thread:
        print("\n  Thread not found.")
        return
    is_pinned = bool(thread.get("is_pinned"))
    action = "Unpin" if is_pinned else "Pin"
    try:
        svc.pin_thread(int(thread_id), pinned=not is_pinned)
        print(f"\n  Thread {action.lower()}ned.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _lock_thread(svc):
    thread_id = input("  Thread ID: ").strip()
    if not thread_id:
        return
    thread = svc.get_thread(int(thread_id))
    if not thread:
        print("\n  Thread not found.")
        return
    is_locked = bool(thread.get("is_locked"))
    action = "Unlock" if is_locked else "Lock"
    try:
        svc.lock_thread(int(thread_id), locked=not is_locked)
        print(f"\n  Thread {action.lower()}ed.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_thread(svc):
    thread_id = input("  Thread ID to delete: ").strip()
    if not thread_id:
        return
    confirm = input("  Delete thread and all posts? (y/n): ").strip().lower()
    if confirm != "y":
        print("\n  Cancelled.")
        return
    try:
        svc.delete_thread(int(thread_id))
        print("\n  Thread and posts deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Posts ───────────────────────────────────────────────────────────────


def _create_post(svc, user_id):
    print_header("Create Post")
    thread_id = input("  Thread ID: ").strip()
    if not thread_id:
        return
    content = input("  Content: ").strip()
    if not content:
        print("\n  Content is required.")
        return
    try:
        post = svc.create_post(int(thread_id), user_id, content)
        print(f"\n  Post created (ID: {post['id']})")
    except Exception as e:
        print(f"\n  Error: {e}")


def _edit_post(svc):
    post_id = input("  Post ID: ").strip()
    if not post_id:
        return
    content = input("  New content: ").strip()
    if not content:
        print("\n  Content is required.")
        return
    try:
        svc.update_post(int(post_id), content)
        print("\n  Post updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_post(svc):
    post_id = input("  Post ID to delete: ").strip()
    if not post_id:
        return
    confirm = input("  Are you sure? (y/n): ").strip().lower()
    if confirm != "y":
        print("\n  Cancelled.")
        return
    try:
        svc.delete_post(int(post_id))
        print("\n  Post deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _mark_solution(svc):
    post_id = input("  Post ID: ").strip()
    if not post_id:
        return
    try:
        post = svc.mark_solution(int(post_id))
        state = "marked" if post.get("is_solution") else "unmarked"
        print(f"\n  Post {state} as solution.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Statistics ──────────────────────────────────────────────────────────


def _forum_stats(svc):
    print_header("Forum Statistics")
    try:
        stats = svc.get_stats()
        print(f"  Total Categories:      {stats['total_categories']}")
        print(f"  Total Threads:         {stats['total_threads']}")
        print(f"  Total Posts:           {stats['total_posts']}")
        print(f"  Active Threads (open): {stats['active_threads']}")
    except Exception as e:
        print(f"\n  Error: {e}")
