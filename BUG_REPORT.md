# Bug Report - Code Review Findings

## Critical Bugs

### 1. **IOC Extraction Order Inconsistency** (models.py)
**Location:** `models.py:32-92` vs `models.py:100-162`

**Issue:** The `extract_iocs()` method extracts domains BEFORE URLs, while `extract_iocs_from_text()` extracts URLs BEFORE domains. This causes inconsistent behavior and duplicate IOC extraction.

**Impact:**
- In `extract_iocs()`: URL `https://evil.com/path` will extract both `evil.com` (as domain) and `https://evil.com/path` (as URL)
- In `extract_iocs_from_text()`: Only the full URL is extracted (correct behavior)

**Lines:**
- `extract_iocs()`: Lines 51-64 (domains), then 59-64 (URLs) ❌
- `extract_iocs_from_text()`: Lines 119-124 (URLs), then 126-132 (domains) ✅

**Fix:** URLs should be checked BEFORE domains in `extract_iocs()` to prevent domain extraction from within URLs.

---

### 2. **Overlapping IOC Highlights** (models.py:165-203)
**Location:** `models.py:165-203`

**Issue:** `extract_iocs_with_positions()` doesn't prevent overlapping highlights. URLs containing domains will have both the URL and domain highlighted, causing visual overlap.

**Impact:** In the TUI, text like `https://evil.com/path` would be highlighted twice - once for the URL and once for `evil.com` as a domain.

**Fix:** Should use the same approach as `extract_iocs_from_text()` - check URLs before domains and use the `seen` set to prevent duplicates based on position ranges.

---

### 3. **Invalid IPv4 Address Matching** (models.py, multiple locations)
**Locations:** Lines 38, 106, 157, 171

**Issue:** IPv4 pattern `r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'` matches invalid IP addresses like `999.999.999.999` because it doesn't validate that octets are in the range 0-255.

**Impact:** False positive IOC detection for invalid IPs that look like version numbers or other numeric patterns.

**Example:** Would match `999.999.999.999`, `300.400.500.600`

**Fix:** Add validation to check each octet is <= 255, or use a more restrictive pattern.

---

## High Priority Issues

### 4. **Subprocess Timeout Missing** (crypto.py:12-18, 67-74)
**Location:** `crypto.py:12-18` and `crypto.py:67-74`

**Issue:** GPG subprocess calls have no timeout parameter. If GPG hangs (e.g., waiting for passphrase), the application will hang indefinitely.

**Impact:** Application freeze if GPG prompts for input or encounters issues.

**Fix:** Add timeout parameter to `communicate()` call:
```python
stdout, stderr = proc.communicate(timeout=10)
```

---

### 5. **Inconsistent Indentation** (storage.py:253)
**Location:** `storage.py:253`

**Issue:** Extra leading space before `return` statement - inconsistent with Python style and could indicate a logic error.

```python
except (json.JSONDecodeError, IOError):
     return {"case_id": None, "evidence_id": None}  # Extra space
```

**Impact:** Style inconsistency, potentially confusing for maintainers.

---

## Medium Priority Issues

### 6. **Inefficient Demo Case Creation** (storage.py:24-180)
**Location:** `storage.py:46-156`

**Issue:** Eight separate `time.sleep(0.1)` calls add 800ms of unnecessary delay during first launch.

**Impact:** Slow first-time startup experience (nearly 1 second added delay).

**Fix:** Either remove the sleeps entirely (timestamp granularity is sufficient) or use a single smaller sleep.

---

### 7. **Missing File Write Error Handling** (cli.py:68-112)
**Location:** `cli.py:68-112`

**Issue:** `export_markdown()` doesn't handle file write errors (disk full, permission denied, etc.).

**Impact:** Uncaught exceptions on export failure, no user feedback.

**Fix:** Wrap file operations in try/except and provide meaningful error messages.

---

### 8. **Incomplete IPv6 Pattern** (models.py:45, 113, 175)
**Locations:** Lines 45, 113, 175

**Issue:** IPv6 pattern `r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'` only matches full format (8 groups), missing compressed format (`::`).

**Impact:** Won't detect compressed IPv6 addresses like `2001:db8::1` or `::1`.

**Example:** Misses `2001:0db8:85a3::8a2e:0370:7334` from demo data (line 146).

---

## Low Priority Issues

### 9. **Hash Collision Risk in IOC Classification** (tui.py:144-162)
**Location:** `tui.py:144-162`

**Issue:** `_classify_ioc()` checks hash lengths in wrong order (MD5, SHA1, SHA256). A SHA256 hash starting with 32 zeros could theoretically match the MD5 pattern first.

**Impact:** Extremely unlikely in practice due to word boundaries, but ordering is still incorrect for clarity.

**Fix:** Check longest hashes first (SHA256, SHA1, MD5).

---

### 10. **No Atomic Write for Settings** (storage.py:264-268)
**Location:** `storage.py:264-268`

**Issue:** `set_setting()` directly writes to settings file without atomic write pattern (temp file + rename) used elsewhere.

**Impact:** Settings corruption if write is interrupted.

**Fix:** Use same atomic write pattern as `save_data()`.

---

### 11. **No Atomic Write for State** (storage.py:239-244)
**Location:** `storage.py:239-244`

**Issue:** `set_active()` directly writes to state file without atomic write pattern.

**Impact:** State corruption if write is interrupted.

**Fix:** Use same atomic write pattern as `save_data()`.

---

## Summary

**Critical:** 3 bugs (IOC extraction, overlapping highlights, invalid IPv4)
**High:** 2 bugs (subprocess timeout, indentation)
**Medium:** 3 issues (inefficient sleeps, missing error handling, IPv6 pattern)
**Low:** 3 issues (hash classification order, non-atomic writes)

**Total:** 11 issues found

## Recommendations

1. **Immediate fixes:** #1 (IOC extraction order), #3 (IPv4 validation), #4 (subprocess timeout)
2. **High priority:** #2 (overlapping highlights), #5 (indentation), #7 (error handling)
3. **Nice to have:** #6 (remove sleeps), #8 (IPv6 support), #9-11 (robustness improvements)
