"""System Monitoring panel — extracted from admin_tools_gui.py so it
can render into either a Toplevel (legacy) or a notebook tab frame
(operations console).

Real-time CPU, memory, disk and DB metrics. 10-second auto-refresh.
"""

import logging
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from education_system.university_system.core.i18n import get_text as _t

logger = logging.getLogger(__name__)


def build_system_monitoring_panel(parent):
    """Render the monitoring dashboard into ``parent`` (any tk container).

    Returns a dict with ``stop`` callable to cancel auto-refresh — the
    operations console invokes this on tab/window destruction so the
    ``after`` loop doesn't outlive its widgets.
    """
    try:
        import psutil
    except ImportError:
        psutil = None

    container = ttk.Frame(parent)
    container.pack(fill=tk.BOTH, expand=True)

    ttk.Label(container, text=_t("admin_tools.monitoring.header"),
              font=('Arial', 16, 'bold')).pack(pady=(10, 5))

    cards_frame = ttk.Frame(container)
    cards_frame.pack(fill=tk.X, padx=10, pady=5)
    for i in range(4):
        cards_frame.columnconfigure(i, weight=1)

    card_labels = {}

    def _make_card(parent_, col, title, initial="--"):
        frame = ttk.LabelFrame(parent_, text=title, padding=10)
        frame.grid(row=0, column=col, padx=5, sticky="nsew")
        val_lbl = ttk.Label(frame, text=initial, font=('Arial', 20, 'bold'))
        val_lbl.pack()
        status_lbl = ttk.Label(frame, text="", font=('Arial', 10))
        status_lbl.pack()
        return val_lbl, status_lbl

    card_labels['cpu'] = _make_card(cards_frame, 0, _t("admin_tools.monitoring.cpu_usage"))
    card_labels['mem'] = _make_card(cards_frame, 1, _t("admin_tools.monitoring.memory_usage"))
    card_labels['disk'] = _make_card(cards_frame, 2, _t("admin_tools.monitoring.disk_usage"))
    card_labels['db'] = _make_card(cards_frame, 3, _t("admin_tools.monitoring.db_status"))

    nb = ttk.Notebook(container)
    nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    health_frame = ttk.Frame(nb, padding=10)
    nb.add(health_frame, text=_t("admin_tools.monitoring.system_health"))
    health_text = tk.Text(health_frame, wrap=tk.WORD, height=15, state=tk.DISABLED,
                          fg="#000000", bg="#FFFFFF")
    health_text.pack(fill=tk.BOTH, expand=True)

    pool_frame = ttk.Frame(nb, padding=10)
    nb.add(pool_frame, text=_t("admin_tools.monitoring.active_connections"))
    pool_text = tk.Text(pool_frame, wrap=tk.WORD, height=15, state=tk.DISABLED,
                        fg="#000000", bg="#FFFFFF")
    pool_text.pack(fill=tk.BOTH, expand=True)

    ttk.Label(container, text=_t("admin_tools.monitoring.auto_refresh"),
              font=('Arial', 9)).pack(pady=(0, 5))

    def _color_for_pct(pct):
        if pct < 70:
            return "#2e7d32"
        if pct < 90:
            return "#f9a825"
        return "#c62828"

    def _status_text(pct):
        if pct < 70:
            return _t("admin_tools.monitoring.status_healthy")
        if pct < 90:
            return _t("admin_tools.monitoring.status_warning")
        return _t("admin_tools.monitoring.status_critical")

    state = {'job': None, 'alive': True}

    def _refresh():
        if not state['alive'] or not container.winfo_exists():
            return
        try:
            if psutil:
                cpu = psutil.cpu_percent(interval=0)
                mem = psutil.virtual_memory().percent
                disk = psutil.disk_usage('/').percent
            else:
                cpu = mem = disk = 0.0

            for key, pct in [('cpu', cpu), ('mem', mem), ('disk', disk)]:
                val_lbl, st_lbl = card_labels[key]
                val_lbl.config(text=f"{pct:.1f}%", foreground=_color_for_pct(pct))
                st_lbl.config(text=_status_text(pct), foreground=_color_for_pct(pct))

            db_ok = False
            try:
                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                conn.execute("SELECT 1")
                conn.close()
                db_ok = True
            except Exception:
                pass

            db_val, db_st = card_labels['db']
            if db_ok:
                db_val.config(text=_t("admin_tools.monitoring.connected"), foreground="#2e7d32")
                db_st.config(text=_t("admin_tools.monitoring.status_healthy"), foreground="#2e7d32")
            else:
                db_val.config(text=_t("admin_tools.monitoring.disconnected"), foreground="#c62828")
                db_st.config(text=_t("admin_tools.monitoring.status_critical"), foreground="#c62828")

            lines = []
            if psutil:
                lines.append(f"CPU Cores: {psutil.cpu_count(logical=True)}")
                vm = psutil.virtual_memory()
                lines.append(f"Total RAM: {vm.total / (1024**3):.1f} GB")
                lines.append(f"Available RAM: {vm.available / (1024**3):.1f} GB")
                du = psutil.disk_usage('/')
                lines.append(f"Disk Total: {du.total / (1024**3):.1f} GB")
                lines.append(f"Disk Free: {du.free / (1024**3):.1f} GB")
                boot = datetime.fromtimestamp(psutil.boot_time())
                lines.append(f"{_t('admin_tools.monitoring.uptime')}: {datetime.now() - boot}")
            else:
                lines.append("psutil not available")

            health_text.config(state=tk.NORMAL)
            health_text.delete("1.0", tk.END)
            health_text.insert("1.0", "\n".join(lines))
            health_text.config(state=tk.DISABLED)

            pool_lines = []
            try:
                from education_system.university_system.infrastructure.database.pool_metrics import get_pool_metrics
                pm = get_pool_metrics()
                stats = pm.get_stats()
                pool_lines.append(f"=== {_t('admin_tools.monitoring.active_connections')} ===")
                pool_lines.append(f"{_t('admin_tools.monitoring.pool_size')}: {stats.get('pool_max_size', 'N/A')}")
                pool_lines.append(f"{_t('admin_tools.monitoring.active')}: {stats.get('active_connections', 'N/A')}")
                pool_lines.append(f"{_t('admin_tools.monitoring.idle')}: {stats.get('idle_connections', 'N/A')}")
                pool_lines.append(f"{_t('admin_tools.monitoring.utilization')}: {stats.get('utilization', 0):.1f}%")
                pool_lines.append("")
                pool_lines.append("=== Cumulative ===")
                pool_lines.append(f"{_t('admin_tools.monitoring.total_created')}: {stats.get('total_connections_created', 0)}")
                pool_lines.append(f"{_t('admin_tools.monitoring.total_closed')}: {stats.get('total_connections_closed', 0)}")
                pool_lines.append(f"{_t('admin_tools.monitoring.total_errors')}: {stats.get('total_errors', 0)}")
                pool_lines.append(f"{_t('admin_tools.monitoring.total_timeouts')}: {stats.get('total_timeouts', 0)}")
                pool_lines.append(f"{_t('admin_tools.monitoring.avg_wait_ms')}: {stats.get('avg_wait_time_ms', 0):.2f}")
                pool_lines.append(f"{_t('admin_tools.monitoring.peak_active')}: {stats.get('peak_active_connections', 0)}")
            except Exception as exc:
                pool_lines.append(f"Pool metrics unavailable: {exc}")

            pool_text.config(state=tk.NORMAL)
            pool_text.delete("1.0", tk.END)
            pool_text.insert("1.0", "\n".join(pool_lines))
            pool_text.config(state=tk.DISABLED)

        except Exception as exc:
            logger.error(f"Monitoring refresh error: {exc}")

        if state['alive'] and container.winfo_exists():
            state['job'] = container.after(10000, _refresh)

    btn_frame = ttk.Frame(container)
    btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
    ttk.Button(btn_frame, text=_t("admin_tools.refresh"),
               command=_refresh).pack(side=tk.LEFT, padx=5)

    def _stop():
        state['alive'] = False
        if state['job'] is not None:
            try:
                container.after_cancel(state['job'])
            except Exception:
                pass

    container.bind("<Destroy>", lambda _e: _stop(), add="+")
    _refresh()

    return {'frame': container, 'stop': _stop}
