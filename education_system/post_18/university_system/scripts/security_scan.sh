#!/bin/bash
#
# Security Scanning Script
# Run comprehensive security checks locally before committing
#
# Usage: ./scripts/security_scan.sh [--fix] [--detailed]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
FIX=false
DETAILED=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --fix)
            FIX=true
            shift
            ;;
        --detailed)
            DETAILED=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--fix] [--detailed]"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Security Scanning Tool${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}⚠ Warning: Virtual environment not activated${NC}"
    echo "Attempting to activate venv..."
    if [[ -d "venv" ]]; then
        source venv/bin/activate
    elif [[ -d ".venv" ]]; then
        source .venv/bin/activate
    else
        echo -e "${RED}✗ No virtual environment found${NC}"
        exit 1
    fi
fi

# Install security tools if not present
echo -e "${BLUE}Checking security tools...${NC}"
pip install -q bandit safety pip-audit 2>/dev/null || {
    echo -e "${YELLOW}Installing security tools...${NC}"
    pip install bandit safety pip-audit
}

# Create reports directory
mkdir -p security-reports
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ============================================================================
# 1. Bandit - Python Security Linter
# ============================================================================
echo ""
echo -e "${BLUE}[1/4] Running Bandit security scan...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if $DETAILED; then
    # Detailed scan (all severity levels)
    bandit -r education_system/university_system/ \
        --exclude education_system/university_system/tests/ \
        -f txt \
        | tee "security-reports/bandit_${TIMESTAMP}.txt"
else
    # Medium and high severity only
    bandit -r education_system/university_system/ \
        --exclude education_system/university_system/tests/ \
        -ll \
        -f txt
fi

BANDIT_EXIT=$?

# Generate JSON report
bandit -r education_system/university_system/ \
    --exclude education_system/university_system/tests/ \
    -f json \
    -o "security-reports/bandit_${TIMESTAMP}.json" \
    2>/dev/null || true

if [ $BANDIT_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ Bandit: No issues found${NC}"
else
    echo -e "${YELLOW}⚠ Bandit: Issues detected (see above)${NC}"
fi

# ============================================================================
# 2. Safety - Dependency Vulnerability Check
# ============================================================================
echo ""
echo -e "${BLUE}[2/4] Running Safety dependency check...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

safety check --full-report | tee "security-reports/safety_${TIMESTAMP}.txt"
SAFETY_EXIT=$?

# Generate JSON report
safety check --json > "security-reports/safety_${TIMESTAMP}.json" 2>/dev/null || true

if [ $SAFETY_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ Safety: No vulnerabilities found${NC}"
else
    echo -e "${RED}✗ Safety: Vulnerabilities detected${NC}"
fi

# ============================================================================
# 3. pip-audit - Additional Vulnerability Scanning
# ============================================================================
echo ""
echo -e "${BLUE}[3/4] Running pip-audit...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

pip-audit | tee "security-reports/pip-audit_${TIMESTAMP}.txt"
PIP_AUDIT_EXIT=$?

# Generate JSON report
pip-audit --format json > "security-reports/pip-audit_${TIMESTAMP}.json" 2>/dev/null || true

if [ $PIP_AUDIT_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ pip-audit: No vulnerabilities found${NC}"
else
    echo -e "${RED}✗ pip-audit: Vulnerabilities detected${NC}"
fi

# ============================================================================
# 4. Custom Security Checks
# ============================================================================
echo ""
echo -e "${BLUE}[4/4] Running custom security checks...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ISSUES_FOUND=0

# Check for hardcoded secrets
echo "  Checking for hardcoded secrets..."
if grep -r -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]" education_system/university_system/ \
    --exclude-dir=tests \
    --exclude-dir=__pycache__ \
    --exclude="*.pyc" 2>/dev/null | grep -v "# nosec" > /dev/null; then
    echo -e "  ${RED}✗ Potential hardcoded secrets found${NC}"
    grep -r -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]" education_system/university_system/ \
        --exclude-dir=tests \
        --exclude-dir=__pycache__ \
        --exclude="*.pyc" 2>/dev/null | grep -v "# nosec" | head -10
    ((ISSUES_FOUND++))
else
    echo -e "  ${GREEN}✓ No hardcoded secrets found${NC}"
fi

# Check for SQL injection risks
echo "  Checking for SQL injection risks..."
if grep -r "execute.*%.*\|.*format.*(" education_system/university_system/ \
    --include="*.py" \
    --exclude-dir=tests 2>/dev/null | grep -v "# nosec" > /dev/null; then
    echo -e "  ${YELLOW}⚠ Potential SQL injection risks found${NC}"
    echo "  (Review string formatting in SQL queries)"
else
    echo -e "  ${GREEN}✓ No SQL injection risks found${NC}"
fi

# Check for debug mode in production
echo "  Checking for debug mode..."
if grep -r "DEBUG\s*=\s*True" education_system/university_system/ \
    --include="*.py" \
    --exclude-dir=tests 2>/dev/null > /dev/null; then
    echo -e "  ${YELLOW}⚠ DEBUG=True found in code${NC}"
else
    echo -e "  ${GREEN}✓ No hardcoded DEBUG=True found${NC}"
fi

# Check for insecure random usage
echo "  Checking for insecure random usage..."
if grep -r "import random$\|from random import" education_system/university_system/infrastructure/security/ \
    --include="*.py" 2>/dev/null | grep -v "# nosec" > /dev/null; then
    echo -e "  ${RED}✗ Insecure random module used in security code${NC}"
    echo "  (Use secrets module instead)"
    ((ISSUES_FOUND++))
else
    echo -e "  ${GREEN}✓ Secure random usage${NC}"
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Security Scan Summary${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

TOTAL_EXIT=$((BANDIT_EXIT + SAFETY_EXIT + PIP_AUDIT_EXIT + ISSUES_FOUND))

if [ $TOTAL_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ All security checks passed!${NC}"
    echo ""
    echo "Reports saved to: security-reports/"
    exit 0
else
    echo -e "${RED}✗ Security issues detected${NC}"
    echo ""
    echo "Summary:"
    echo "  Bandit: $([ $BANDIT_EXIT -eq 0 ] && echo -e \"${GREEN}PASS${NC}\" || echo -e \"${RED}FAIL${NC}\")"
    echo "  Safety: $([ $SAFETY_EXIT -eq 0 ] && echo -e \"${GREEN}PASS${NC}\" || echo -e \"${RED}FAIL${NC}\")"
    echo "  pip-audit: $([ $PIP_AUDIT_EXIT -eq 0 ] && echo -e \"${GREEN}PASS${NC}\" || echo -e \"${RED}FAIL${NC}\")"
    echo "  Custom checks: $([ $ISSUES_FOUND -eq 0 ] && echo -e \"${GREEN}PASS${NC}\" || echo -e \"${RED}FAIL${NC}\")"
    echo ""
    echo "Reports saved to: security-reports/"
    echo ""
    echo "To fix issues:"
    echo "  - Review the reports above"
    echo "  - Update vulnerable dependencies"
    echo "  - Fix code security issues"
    echo "  - Use 'pip install --upgrade' for dependency updates"
    exit 1
fi
