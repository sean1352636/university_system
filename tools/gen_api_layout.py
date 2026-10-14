#!/usr/bin/env python3
"""Generate PROPOSED_API_LAYOUT.txt from the real on-disk API inventory.

The consolidation is done: every system's HTTP surface now lives under
``src/education_system/api/``. What this still proposes is the *shape inside*
each package - grouping the flat route modules into routes/<group>/ and
filling in schemas/.
"""
import os, re, subprocess
from collections import defaultdict

ROOT = os.path.expanduser("~/projects/education-system")
DATE = subprocess.run(["date", "+%Y-%m-%d"], capture_output=True,
                      text=True).stdout.strip()
HEAD = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                      capture_output=True, text=True).stdout.strip() or "unknown"
SRC = os.path.join(ROOT, "src/education_system")

def files(rel):
    p = os.path.join(SRC, rel)
    out = []
    for dp, dn, fn in os.walk(p):
        for f in fn:
            out.append(os.path.relpath(os.path.join(dp, f), p))
    return sorted(out)

# ---------------------------------------------------------------- grouping
SCHOOL_RULES = [
 ("pupils",       ["children","pupils_","students_","admissions","enrolment","leavers","transition",
                   "emergency_contacts","parent_contacts","key_persons","occupancy","settling_in",
                   "student_routes"]),
 ("attendance",   ["attendance","daily_register","sign_in_out","absence"]),
 ("safeguarding", ["safeguarding","dsl_","concerns","prevent_duty","looked_after","welfare",
                   "consents","emergency_routes","risk_assessments","accident","existing_injuries","first_aid","medication",
                   "medical","allergies","health_safety","ratios","visitors","dbs_checks"]),
 ("assessment",   ["assessment","progress_check","progress_report","progress_","target_setting",
                   "ks1_sats","ks2_sats","mtc_","phonics_screening","cohort_tracking","reading_levels",
                   "eyfs_profile"]),
 ("curriculum",   ["curriculum","lesson_plans","subjects","homework","phonics","library",
                   "learning_journeys","effective_learning","development_tracking","next_steps",
                   "observations","evidence","academics","academic_year","timetable","calendar","classes",
                   "class_teachers","year_groups","departments","rooms_"]),
 ("pastoral",     ["wellbeing","behaviour","house_points","clubs","trips","school_council",
                   "early_warning","intervention","pupil_support","send_routes","ehc_plans",
                   "accessibility","feedback","surveys","transport","wraparound","meals",
                   "sleep_log","toileting","bottle_feeds","daily_diary","daily_updates",
                   "activity_feed","student_services","pastoral_routes"]),
 ("progression",  ["progression"]),
 ("staff",        ["staff","appraisals","cpd_","recruitment","rota","cover_","teaching_assistants",
                   "qualifications","staff_hr","expense_claims"]),
 ("finance",      ["finance","funding","funded_hours","invoices","payments","receipts",
                   "dinner_money","discounts","childcare_vouchers","pupil_premium"]),
 ("comms",        ["messag","newsletters","announcements","notifications","letter_templates",
                   "parents_evenings","parent_meetings","document_hub","attachments","assets_",
                   "todo_","staff_comms"]),
 ("governance",   ["governance","policies","compliance","ofsted","complaints","gdpr","equality",
                   "audit","census","data_export","custom_export","user_management",
                   "risk_management","legal"]),
 ("reports",      ["report","dashboard","kpi_","analytics","advanced_search"]),
]

UNI_RULES = {
 "academics": [
   ("teaching",  ["course","module","degree","timetable","calendar","office_hours",
                  "virtual_classroom","ta_routes","library","assignment","exam","attendance",
                  "absence"]),
   ("research",  ["research","collaborative_provision","student_mobility","quality_assurance","qa_"]),
   ("study",     ["ai_features","ai_study","study_group","study_matching","study_recommendation"]),
   ("progress",  ["academic_progress","evaluation","integrity","parent_routes","academics_domain"]),
 ],
 "operations": [
   ("commerce",  ["barber","betting","butcher","carrental","cinema","commerce","dining","gym",
                  "marketplace","musicshop","nailbar","phoneshop","printing","textbooks"]),
   ("campus",    ["campus","facility","facilities_mgmt","parking","security","lost_found","mail",
                  "equipment","study_rooms"]),
   ("housing",   ["housing","roommate_finder","mobility"]),
   ("events",    ["event"]),
   ("platform",  ["institutional_analytics","feedback_system","operations_routes","log_management"]),
 ],
 "pastoral": [
   ("wellbeing", ["counseling","health","dentist","wellness","student_wellbeing","emergency",
                  "accessibility"]),
   ("support",   ["advising","mentorship","tutoring","early_warning","helpdesk","student_affairs"]),
   ("careers",   ["career","student_jobs","achievement_badge"]),
   ("community", ["club","election","social_matching","accommodation","student_app"]),
 ],
}

def group(name, rules):
    for g, keys in rules:
        for k in keys:
            if k in name:
                return g
    return "_misc"

# ---------------------------------------------------------------- tree render
def render(node, prefix="", out=None):
    if out is None: out = []
    items = sorted(node.items(), key=lambda kv: (not isinstance(kv[1], dict), kv[0]))
    for i, (name, val) in enumerate(items):
        last = i == len(items) - 1
        conn = "└── " if last else "├── "
        if isinstance(val, dict):
            out.append(prefix + conn + name + "/")
            render(val, prefix + ("    " if last else "│   "), out)
        else:
            line = prefix + conn + name
            if val:
                line = line + " " * max(2, 62 - len(line)) + val
            out.append(line)
    return out

def T():
    return defaultdict(T)

def put(tree, path, note=""):
    parts = path.split("/")
    n = tree
    for p in parts[:-1]:
        n = n[p]
    n[parts[-1]] = note

# ================================================================ PLATFORM
P = "platform/delivery/api"
PLATFORM_MOVES = [
 # (old rel path under platform/delivery/api, new path under src/education_system, note)
 ("__init__.py",            P+"/__init__.py",                    "exports create_app() only"),
 ("unified_server.py",      P+"/app.py",                         "app factory; serving moves to launcher/"),
 (None,                     P+"/registry.py",                    "NEW - the single mount table"),
 (None,                     P+"/versioning.py",                  "NEW - API_VERSION + legacy redirects"),

 ("errors.py",              P+"/kernel/errors.py",               "merge with university/errors.py"),
 ("university/errors.py",   P+"/kernel/errors.py",               "MERGED - delete dupe"),
 (None,                     P+"/kernel/problems.py",             "NEW - RFC 7807 payload shapes"),
 ("pagination.py",          P+"/kernel/pagination.py",           "merge with university/pagination.py"),
 ("university/pagination.py", P+"/kernel/pagination.py",         "MERGED - delete dupe"),
 ("validators.py",          P+"/kernel/validation.py",           "merge x3"),
 ("request_validator.py",   P+"/kernel/validation.py",           "MERGED - PayloadValidationError"),
 ("university/validators.py", P+"/kernel/validation.py",         "MERGED - delete dupe"),
 ("content_negotiation.py", P+"/kernel/responses.py",            "envelope + negotiation"),
 ("async_adapter.py",       P+"/kernel/async_adapter.py",        "unchanged"),
 ("base_config.py",         P+"/kernel/config.py",               "merge with university/config.py"),
 ("university/config.py",   P+"/kernel/config.py",               "MERGED - delete dupe"),
 ("static_files.py",        P+"/kernel/static_files.py",         "safe static serving"),

 ("jwt_utils.py",           P+"/security/jwt.py",                "encode/decode/refresh"),
 ("auth.py",                P+"/security/authentication.py",     "SPLIT - helpers here"),
 ("university/auth.py",     P+"/security/principals.py",         "128 importers - keep shim"),
 ("api_keys.py",            P+"/security/api_keys.py",           "unchanged"),
 (None,                     P+"/security/decorators.py",         "NEW - require_staff/authorize_object"),
 ("security_headers.py",    P+"/security/headers.py",            "unchanged"),

 (None,                     P+"/middleware/__init__.py",         "NEW - declares apply order"),
 ("middleware.py",          P+"/middleware/request_context.py",  "request_id, g, logging"),
 ("tenant_middleware.py",   P+"/middleware/tenant.py",           "unchanged"),
 ("rate_limiter.py",        P+"/middleware/rate_limit.py",       "unchanged"),
 ("caching.py",             P+"/middleware/caching.py",          "unchanged"),
 (None,                     P+"/middleware/csrf.py",             "NEW - wraps governance/security/csrf"),

 ("university/openapi_spec.py", P+"/openapi/spec.py",            "generate FROM registry.py"),
 ("university/core_api.py", P+"/openapi/spec.py",                "MERGED"),
 ("docs.py",                P+"/openapi/ui.py",                  "Swagger UI blueprint"),

 ("graphql/__init__.py",    P+"/graphql/__init__.py",            ""),
 ("graphql/schema.py",      P+"/graphql/schema.py",              ""),
 ("graphql/types.py",       P+"/graphql/types.py",               ""),
 ("graphql/resolvers.py",   P+"/graphql/resolvers.py",           "delegate to services, not SQL"),
 ("graphql/mutations.py",   P+"/graphql/mutations.py",           ""),
 ("graphql/middleware.py",  P+"/graphql/middleware.py",          ""),

 ("websocket_server.py",    P+"/realtime/socketio.py",           "init_socketio()"),
 (None,                     P+"/realtime/namespaces.py",         "NEW - one class per namespace"),

 ("auth.py",                P+"/routes/auth_routes.py",          "SPLIT - auth_bp lives here"),
 ("health.py",              P+"/routes/health_routes.py",        "liveness/readiness"),
 ("metrics_routes.py",      P+"/routes/metrics_routes.py",       ""),
 ("admin_control.py",       P+"/routes/admin_control_routes.py", ""),
 ("tenant_routes.py",       P+"/routes/tenant_routes.py",        ""),
 ("retention_routes.py",    P+"/routes/retention_routes.py",     ""),
 ("warehouse_routes.py",    P+"/routes/warehouse_routes.py",     ""),
 ("webhook_routes.py",      P+"/routes/webhook_routes.py",       ""),
 ("journey_routes.py",      P+"/routes/journey_routes.py",       "cross-system learner journey"),
 ("lms_routes.py",          "DELETE",                            "internal LMS retired - see migration c7a3e91f4d20"),
]

WEB_MOVES = [
 ("web/__init__.py",              "platform/delivery/web/__init__.py",              ""),
 ("web/routes.py",                "platform/delivery/web/portal/routes.py",         ""),
 ("web/pwa.py",                   "platform/delivery/web/portal/pwa.py",            ""),
 ("web/portal/index.html",        "platform/delivery/web/portal/templates/index.html", ""),
 ("web/portal/login.html",        "platform/delivery/web/portal/templates/login.html", ""),
 ("web/portal/dashboard.html",    "platform/delivery/web/portal/templates/dashboard.html", ""),
 ("web/portal/module.html",       "platform/delivery/web/portal/templates/module.html", ""),
 ("web/portal/students.html",     "platform/delivery/web/portal/templates/students.html", ""),
 ("web/portal/assets/portal.css", "platform/delivery/web/portal/static/css/portal.css", ""),
 ("web/portal/assets/portal.js",  "platform/delivery/web/portal/static/js/portal.js", ""),
 ("web/static/css/style.css",     "platform/delivery/web/portal/static/css/style.css", ""),
 ("web/static/js/app.js",         "platform/delivery/web/portal/static/js/app.js",  ""),
 ("web/static/js/modules/primary.js",  "platform/delivery/web/portal/static/js/modules/primary.js", ""),
 ("web/static/js/modules/secondary.js","platform/delivery/web/portal/static/js/modules/secondary.js", ""),
 ("web/static/js/modules/shared_components.js","platform/delivery/web/portal/static/js/modules/shared_components.js",""),
 ("web/static/js/modules/websocket.js","platform/delivery/web/portal/static/js/modules/websocket.js", ""),
 ("parent_portal/__init__.py",    "platform/delivery/web/parent_portal/__init__.py", ""),
 ("parent_portal/routes.py",      "platform/delivery/web/parent_portal/routes.py",   ""),
 ("parent_portal/static/manifest.json","platform/delivery/web/parent_portal/static/manifest.json",""),
 ("parent_portal/static/sw.js",   "platform/delivery/web/parent_portal/static/sw.js", ""),
 ("parent_portal/static/css/parent.css","platform/delivery/web/parent_portal/static/css/parent.css",""),
 ("parent_portal/static/js/parent_app.js","platform/delivery/web/parent_portal/static/js/parent_app.js",""),
]
# university web assets - already moved; inventory them where they now live
for f in files("platform/delivery/web/university"):
    WEB_MOVES.append(("university/static/" + os.path.basename(f),
                      "platform/delivery/web/university/" + f,
                      ""))

# ================================================================ SYSTEMS
GROUPED = ["nursery", "primary", "secondary", "sixth_form"]
FLAT    = ["fe_college", "apprenticeships"]
API     = "api"                     # src/education_system/api/ - the single root

def flat_py(rel):
    """Route modules sitting directly in *rel* - never the grouped stubs below."""
    return [f for f in files(rel)
            if f.endswith(".py") and f != "__init__.py" and "/" not in f]

def is_stub(rel, f):
    """True for an empty scaffold placeholder, false for real code."""
    try:
        with open(os.path.join(SRC, rel, f), encoding="utf-8") as fh:
            return "Not yet implemented." in fh.read(400)
    except OSError:
        return False

def placed_py(rel):
    """Real route modules already filed into a routes/<group>/ subdirectory."""
    return [f for f in files(rel)
            if f.endswith(".py") and os.path.basename(f) != "__init__.py"
            and "/" in f and not is_stub(rel, f)]

sys_trees, sys_moves, sys_counts = {}, [], {}

for s in GROUPED:
    base = f"{API}/{s}"
    t = T()
    put(t, "__init__.py", "SYSTEM_BLUEPRINTS + blueprint()")
    put(t, "dependencies.py", "NEW - db/service wiring (was init_* funcs)")
    n = 0
    for f in flat_py(base + "/routes"):
        g = group(f, SCHOOL_RULES)
        put(t, f"routes/{g}/{f}", "")
        sys_moves.append((f"{base}/routes/{f}", f"{base}/routes/{g}/{f}"))
        n += 1
    for f in placed_py(base + "/routes"):
        put(t, f"routes/{f}", "in place")
        n += 1
    for g in sorted({group(f, SCHOOL_RULES) for f in flat_py(base + "/routes")}
                    | {f.split("/")[0] for f in placed_py(base + "/routes")}):
        put(t, f"routes/{g}/__init__.py", "NEW - group blueprint")
        put(t, f"schemas/{g}.py", "NEW - pydantic models")
    put(t, "routes/__init__.py", "aggregates group blueprints")
    put(t, "schemas/__init__.py", "NEW")
    for f in flat_py(base):
        if f not in ("dependencies.py",):
            put(t, f, "existing module")
    sys_trees[s] = t
    sys_counts[s] = n

for s in FLAT:
    base = f"{API}/{s}"
    t = T()
    put(t, "__init__.py", "SYSTEM_BLUEPRINTS + blueprint()")
    put(t, "dependencies.py", "NEW - db/service wiring")
    n = 0
    for f in files(base + "/routes"):
        if not f.endswith(".py") or "/" in f:
            continue
        note = "renamed from router.py" if f == "router.py" else ""
        put(t, f"routes/{'__init__.py' if f=='router.py' else f}", note)
        n += 0 if f in ("__init__.py", "router.py") else 1
    for f in files(base + "/schemas"):
        if f.endswith(".py") and "/" not in f:
            put(t, f"schemas/{f}", "")
    for f in flat_py(base):
        if f not in ("dependencies.py",):
            put(t, f, "existing module")
    sys_trees[s] = t
    sys_counts[s] = n

# --- university domains
uni_tree = T()
uni_counts = {}
UNI_BASE = f"{API}/university"
for d in sorted(os.listdir(os.path.join(SRC, UNI_BASE))):
    apidir = f"{UNI_BASE}/{d}"
    if not os.path.isdir(os.path.join(SRC, apidir)):
        continue
    rules = UNI_RULES.get(d)
    n = 0
    for f in flat_py(apidir):
        if rules:
            g = group(f, rules)
            dest = f"{d}/routes/{g}/{f}"
        else:
            dest = f"{d}/routes/{f}"
        put(uni_tree, dest, "")
        sys_moves.append((f"{apidir}/{f}", f"{UNI_BASE}/{dest}"))
        n += 1
    for f in placed_py(f"{apidir}/routes"):
        put(uni_tree, f"{d}/routes/{f}", "in place")
        n += 1
    put(uni_tree, f"{d}/__init__.py", "DOMAIN_BLUEPRINTS")
    put(uni_tree, f"{d}/routes/__init__.py", "")
    put(uni_tree, f"{d}/schemas/__init__.py", "NEW - pydantic models")
    if rules:
        for g in sorted({group(f, rules) for f in flat_py(apidir)}
                        | {f.split("/")[0] for f in placed_py(f"{apidir}/routes")}):
            put(uni_tree, f"{d}/routes/{g}/__init__.py", "")
            put(uni_tree, f"{d}/schemas/{g}.py", "NEW")
    uni_counts[d] = n

# log_management is the one stray still outside api/ - see the notes below
put(uni_tree, "operations/routes/platform/log_management_routes.py",
    "TODO <- infrastructure/logging/log_management/api/")
uni_counts["operations"] += 1

# ================================================================ ASSEMBLE
plat = T()
seen = set()
for old, new, note in PLATFORM_MOVES:
    if new == "DELETE" or new in seen:
        continue
    seen.add(new)
    put(plat, new[len(P)+1:], note)

web = T()
seen_w = set()
for old, new, note in WEB_MOVES:
    if new in seen_w: continue
    seen_w.add(new)
    put(web, new[len("platform/delivery/web")+1:], note)

def block(title, tree, root):
    L = ["", title, "=" * len(title), "", root]
    L += render(tree)
    return L

O = []
A = O.append
BAR = "=" * 78
A(BAR)
A("API LAYOUT - education-system")
A(f"Generated {DATE} from the on-disk inventory at HEAD {HEAD}")
A(BAR)
A("""
THE ORGANISING RULE
-------------------
  src/education_system/api/  is the single HTTP surface. One package per
  system; university adds one package per domain beneath it.
  platform/delivery/api/  is a KERNEL - hosting, middleware, security.
  The dependency runs api/ -> kernel, never the other way.
  registry.py is the ONE place blueprints are mounted.

WHAT CHANGED
------------
  The seven systems previously kept their routes at
  systems/<s>/interfaces/api/, and university split them again across
  domains/<d>/interfaces/api/. All of it now lives under api/, so one
  registry loop can mount every system and one import-linter contract can
  guard the whole boundary. systems/<s>/interfaces/ keeps cli/ and gui/.

WHAT THIS DOCUMENT STILL PROPOSES
---------------------------------
  The move is done; the shape inside each package is not. Route modules
  still sit flat in routes/, beside empty grouped stubs at routes/<group>/.
  The trees below show where each flat module should land, and which
  schemas/ modules remain to be written.

STATE AT TIME OF WRITING
------------------------
  * The university API surface was deleted deliberately on 2026-09-08
    (backup: var/backups/maintenance/api-removal-20260908_204628) to be
    rebuilt module by module. The domain route modules below exist on disk
    but NOTHING registers them - registry.py still names the pre-move path
    education_system.systems.university.interfaces.api.routes, which does
    not exist. Point it at education_system.api.university.<domain> as the
    rebuild lands.
  * platform/delivery/api/university/{auth,pagination,validators}.py are
    intentionally still present - 128 modules import them. They are a
    library, not an API surface, which is exactly why they belong in
    kernel/ and security/ rather than in a university-named folder. Note
    this is a DIFFERENT package from api/university/, which holds routes.
  * fe_college and apprenticeships have complete routes/ + schemas/ trees
    that unified_server.py never registers, and they are missing from the
    legacy-redirect prefix list. They are unreachable today.
""")

O += block("1. PLATFORM API KERNEL", plat, "src/education_system/platform/delivery/api/")
A("""
  registry.py holds the entire URL surface as data:

      SYSTEMS = [
          Mount("university", "/api/v1/university", university_blueprints),
          Mount("sixthform",  "/api/v1/sixthform",  sixth_form_blueprints),
          Mount("school",     "/api/v1/school",     secondary_blueprints),
          Mount("primary",    "/api/v1/primary",    primary_blueprints),
          Mount("nursery",    "/api/v1/nursery",    nursery_blueprints),
          Mount("fecollege",  "/api/v1/fecollege",  fe_college_blueprints),   # unwired today
          Mount("apprentice", "/api/v1/apprentice", apprenticeship_blueprints), # unwired today
      ]

  That single list is what app.py mounts, what openapi/spec.py walks, and
  what an authz-coverage test iterates. With ~378 IDOR routes and ~10 gates
  wired, "every route has a capability gate" becomes a test, not a grep.
""")

O += block("2. WEB DELIVERY (moved out of the API package)", web,
           "src/education_system/platform/delivery/web/")
A("""
  Static HTML, PWA manifests and service workers are a different delivery
  channel from JSON endpoints. They become a sibling of api/, not a child.
  parent_portal/ and university/static/ are the two trees this rescues.
""")

for s in GROUPED + FLAT:
    label = s.replace("_", " ").upper()
    O += block(f"3.{GROUPED.index(s)+1 if s in GROUPED else len(GROUPED)+FLAT.index(s)+1}"
               f" {label}  ({sys_counts[s]} route modules)",
               sys_trees[s], f"src/education_system/{API}/{s}/")

O += block(f"4. UNIVERSITY DOMAIN SLICES  ({sum(uni_counts.values())} route modules)",
           uni_tree, f"src/education_system/{API}/university/")
A("")
A("  Per-domain module counts:")
for d, n in sorted(uni_counts.items(), key=lambda kv: -kv[1]):
    A(f"      {d:<14} {n:>3}")

A("""
NOTES ON THE UNIVERSITY SLICES
------------------------------
  * Every domain has routes/ and schemas/ so it matches the other six
    systems exactly. The *_routes.py still sit flat at api/university/<d>/;
    the tree above shows the routes/<group>/ slot each one belongs in.
  * academics, operations and pastoral are large enough to warrant route
    subgroups; the other seven stay flat.
  * operations/routes/commerce/ collects the campus-trading modules
    (barber, betting, butcher, carrental, cinema, dining, gym, marketplace,
    musicshop, nailbar, phoneshop, printing, textbooks). They share one
    wallet/ledger concern and should share one schema module.
  * One stray is DONE: external_quality_assurance/api/qa_routes.py now sits
    at api/university/academics/routes/research/quality_assurance_routes.py.
    That also cleared its entry from the _FLASK_IN_DOMAIN ratchet in
    tests/unit/systems/university/domains/academics/test_academics_boundaries.py.
  * One stray REMAINS, deliberately:
      systems/university/infrastructure/logging/log_management/api/
    It is not a route package but a self-contained Flask mini-app - its
    __init__.py builds `app`, auth.py and routes.py import back from it, and
    the parent log_management/__init__.py does `from ...api import app`.
    Moving it needs a real refactor, not a rename: routes.py becomes
    operations/routes/platform/log_management_routes.py and api/auth.py
    folds into platform security/principals.py.
""")
A(BAR)
A("5. FILE-BY-FILE MOVE MAP - platform/delivery/api/")
A(BAR)
A("")
A(f"  {'FROM (platform/delivery/api/)':<32} {'TO':<44}")
A(f"  {'-'*32} {'-'*44}")
for old, new, note in PLATFORM_MOVES:
    if old is None:
        A(f"  {'(new file)':<32} {new}")
    else:
        A(f"  {old:<32} {new}")
A("")
A("  Web-channel moves:")
for old, new, note in WEB_MOVES:
    A(f"  {old:<44} -> {new}")

A("")
A(BAR)
A("6. INVARIANTS WORTH ENFORCING IN CI")
A(BAR)
A("""
  a. platform/delivery/api/** must not import education_system.systems.**
     (import-linter contract; ~10 lines. This is the rule that stops
     api/university/ from growing back.)
  b. api/<system>/** must not import another system's package, and
     api/** must not be imported BY platform/delivery/api/**.
  c. Every blueprint reachable from registry.py appears in openapi/spec.py.
  d. Every route function carries a capability gate from
     security/decorators.py - enumerate via registry.py, not grep.
  e. No module under api/ opens a DB connection directly;
     routes call services. (Catches the pagination/N+1 class early.)
  f. No inline on*= event-handler attributes under delivery/web/.
     ENFORCED: tests/contract/platform/test_no_inline_event_handlers.py,
     wired into the contracts job. Pages ship with script-src 'self' (portal
     pages add a nonce, which does NOT cover handler attributes), so an
     onclick="" is dead in the browser with no server-side signal at all -
     it took the theme toggle, Sign out, the MFA back button and five
     parent-portal buttons out before anyone noticed.
""")
A(BAR)
A("7. SUGGESTED SEQUENCE")
A(BAR)
A("""
  1. Create kernel/ + security/ + middleware/ and collapse the four
     duplicated pairs. Leave shims at the old paths - 128 modules import
     platform/delivery/api/university/auth.py.
  2. Add registry.py + app.py; have unified_server.py delegate to them so
     nothing changes behaviourally yet.
  3. Move web/ + parent_portal/ + university/static/ out to delivery/web/.
  4. DONE - all seven systems consolidated under src/education_system/api/.
  5. File each flat route module into its routes/<group>/ slot, replacing
     the empty stub - start with secondary (9 modules) to prove the shape,
     then nursery/primary.
  6. Point registry.py at education_system.api.university.<domain> as the
     university rebuild lands, one domain at a time.
  7. Wire fe_college and apprenticeships into registry.py - they are
     already complete and simply unreachable.
  8. Refactor the log_management mini-app out to operations/routes/platform/.
  9. Turn on the import-linter contracts (6a, 6b) last, once green.
""")
A(BAR)

out = os.path.join(ROOT, "PROPOSED_API_LAYOUT.txt")
with open(out, "w") as fh:
    fh.write("\n".join(O) + "\n")
print("wrote", out, sum(1 for _ in open(out)), "lines")
