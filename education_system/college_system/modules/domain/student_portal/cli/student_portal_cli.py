"""Student Portal CLI module for managing portal pages and quick links."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.student_portal.services.student_portal_service import StudentPortalService
from education_system.college_system.infrastructure.auth.core import UserAuth


def student_portal_menu(auth: UserAuth):
    """Student Portal management menu."""
    svc = StudentPortalService(auth._db_path)

    while True:
        print_header("Student Portal")
        options = [
            ("1", "List Pages"),
            ("2", "View Page"),
            ("3", "New Page"),
            ("4", "Update Page"),
            ("5", "Toggle Publish"),
            ("6", "Delete Page"),
            ("7", "List Links"),
            ("8", "New Link"),
            ("9", "Update Link"),
            ("10", "Toggle Active"),
            ("11", "Delete Link"),
            ("12", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break

        # ── Pages ──

        elif choice == "1":
            cat = input("  Filter by category (blank for all): ").strip() or None
            search = input("  Search term (blank for all): ").strip() or None
            pages = svc.list_pages(category=cat, search=search)
            if not pages:
                print("\n  No pages found.")
            else:
                for p in pages:
                    pub = "Published" if p.get("is_published") else "Draft"
                    print(f"  [{p['id']}] {p.get('page_title', '')} "
                          f"({p.get('page_slug', '')}) [{p.get('category', '')}] "
                          f"- {pub}")

        elif choice == "2":
            try:
                pid = int(input("  Page ID: ").strip())
                page = svc.get_page(pid)
                if not page:
                    print("\n  Page not found.")
                else:
                    print(f"\n  Title:     {page.get('page_title', '')}")
                    print(f"  Slug:      {page.get('page_slug', '')}")
                    print(f"  Category:  {page.get('category', '')}")
                    print(f"  Published: {'Yes' if page.get('is_published') else 'No'}")
                    print(f"  Sort:      {page.get('sort_order', 0)}")
                    print(f"  Created:   {page.get('created_at', '')}")
                    print(f"  Updated:   {page.get('updated_at', '')}")
                    content = page.get("content") or "(empty)"
                    print(f"  Content:\n    {content}")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "3":
            try:
                title = input("  Page title: ").strip()
                slug = input("  Page slug: ").strip()
                if not title or not slug:
                    print("\n  Title and slug are required.")
                    continue
                content = input("  Content (optional): ").strip() or None
                category = input("  Category (general): ").strip() or "general"
                sort_order = input("  Sort order (0): ").strip()
                try:
                    so = int(sort_order) if sort_order else 0
                except ValueError:
                    so = 0
                page = svc.create_page(
                    title, slug, content=content, category=category, sort_order=so,
                )
                print(f"\n  Page #{page['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "4":
            try:
                pid = int(input("  Page ID to update: ").strip())
                page = svc.get_page(pid)
                if not page:
                    print("\n  Page not found.")
                    continue
                print(f"  Current title: {page.get('page_title', '')}")
                title = input("  New title (Enter to keep): ").strip() or None
                print(f"  Current slug: {page.get('page_slug', '')}")
                slug = input("  New slug (Enter to keep): ").strip() or None
                print(f"  Current category: {page.get('category', '')}")
                category = input("  New category (Enter to keep): ").strip() or None
                content = input("  New content (Enter to keep): ").strip() or None
                sort_order = input("  New sort order (Enter to keep): ").strip()
                kwargs = {}
                if title:
                    kwargs["page_title"] = title
                if slug:
                    kwargs["page_slug"] = slug
                if category:
                    kwargs["category"] = category
                if content:
                    kwargs["content"] = content
                if sort_order:
                    try:
                        kwargs["sort_order"] = int(sort_order)
                    except ValueError:
                        pass
                if not kwargs:
                    print("\n  No changes provided.")
                    continue
                updated = svc.update_page(pid, **kwargs)
                print(f"\n  Page #{updated['id']} updated.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            try:
                pid = int(input("  Page ID to toggle: ").strip())
                page = svc.toggle_publish(pid)
                status = "Published" if page.get("is_published") else "Draft"
                print(f"\n  Page #{page['id']} is now: {status}")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            try:
                pid = int(input("  Page ID to delete: ").strip())
                confirm = input(f"  Delete page #{pid}? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_page(pid)
                    print(f"\n  Page #{pid} deleted.")
                else:
                    print("\n  Cancelled.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        # ── Links ──

        elif choice == "7":
            cat = input("  Filter by category (blank for all): ").strip() or None
            search = input("  Search term (blank for all): ").strip() or None
            links = svc.list_links(category=cat, search=search)
            if not links:
                print("\n  No links found.")
            else:
                for lnk in links:
                    active = "Active" if lnk.get("is_active") else "Inactive"
                    print(f"  [{lnk['id']}] {lnk.get('link_title', '')} "
                          f"-> {lnk.get('url', '')} [{lnk.get('category', '')}] "
                          f"- {active}")

        elif choice == "8":
            try:
                title = input("  Link title: ").strip()
                url = input("  URL: ").strip()
                if not title or not url:
                    print("\n  Title and URL are required.")
                    continue
                category = input("  Category (useful_links): ").strip() or "useful_links"
                description = input("  Description (optional): ").strip() or None
                icon = input("  Icon (optional): ").strip() or None
                sort_order = input("  Sort order (0): ").strip()
                try:
                    so = int(sort_order) if sort_order else 0
                except ValueError:
                    so = 0
                link = svc.create_link(
                    title, url, category=category, description=description,
                    icon=icon, sort_order=so,
                )
                print(f"\n  Link #{link['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            try:
                lid = int(input("  Link ID to update: ").strip())
                link = svc.get_link(lid)
                if not link:
                    print("\n  Link not found.")
                    continue
                print(f"  Current title: {link.get('link_title', '')}")
                title = input("  New title (Enter to keep): ").strip() or None
                print(f"  Current URL: {link.get('url', '')}")
                url = input("  New URL (Enter to keep): ").strip() or None
                print(f"  Current category: {link.get('category', '')}")
                category = input("  New category (Enter to keep): ").strip() or None
                description = input("  New description (Enter to keep): ").strip() or None
                sort_order = input("  New sort order (Enter to keep): ").strip()
                kwargs = {}
                if title:
                    kwargs["link_title"] = title
                if url:
                    kwargs["url"] = url
                if category:
                    kwargs["category"] = category
                if description:
                    kwargs["description"] = description
                if sort_order:
                    try:
                        kwargs["sort_order"] = int(sort_order)
                    except ValueError:
                        pass
                if not kwargs:
                    print("\n  No changes provided.")
                    continue
                updated = svc.update_link(lid, **kwargs)
                print(f"\n  Link #{updated['id']} updated.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "10":
            try:
                lid = int(input("  Link ID to toggle: ").strip())
                link = svc.toggle_active(lid)
                status = "Active" if link.get("is_active") else "Inactive"
                print(f"\n  Link #{link['id']} is now: {status}")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "11":
            try:
                lid = int(input("  Link ID to delete: ").strip())
                confirm = input(f"  Delete link #{lid}? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_link(lid)
                    print(f"\n  Link #{lid} deleted.")
                else:
                    print("\n  Cancelled.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        # ── Statistics ──

        elif choice == "12":
            try:
                stats = svc.get_stats()
                print("\n  === Portal Statistics ===")
                print(f"  Total Pages:    {stats['total_pages']}")
                print(f"  Published:      {stats['published']}")
                print(f"  Draft:          {stats['draft']}")
                print(f"  Total Links:    {stats['total_links']}")
                print(f"  Active Links:   {stats['active_links']}")
                print(f"  Inactive Links: {stats['inactive_links']}")
                if stats["pages_by_category"]:
                    print("\n  Pages by Category:")
                    for cat, cnt in stats["pages_by_category"].items():
                        print(f"    {cat}: {cnt}")
                if stats["links_by_category"]:
                    print("\n  Links by Category:")
                    for cat, cnt in stats["links_by_category"].items():
                        print(f"    {cat}: {cnt}")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
