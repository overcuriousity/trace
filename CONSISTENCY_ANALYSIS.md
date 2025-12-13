# Menu Interface Consistency Analysis

## Summary
Investigation of key bindings and behavior across all views in the trace TUI application to identify inconsistencies and improve user experience.

## Views in the Application
1. **case_list** - Main list of cases
2. **case_detail** - Case details with evidence list and case notes
3. **evidence_detail** - Evidence details with notes
4. **tags_list** - List of tags with usage counts
5. **tag_notes_list** - List of notes containing a specific tag
6. **ioc_list** - List of IOCs with usage counts
7. **ioc_notes_list** - List of notes containing a specific IOC
8. **note_detail** - Full view of a single note
9. **help** - Help screen

---

## ✅ What's CONSISTENT and Working Well

### Global Keys (work everywhere)
- **`?` or `h`**: Open help - Works from any view ✓
- **`q`**: Quit (or close help if in help view) ✓
- **`b`**: Back/navigate up hierarchy - Works consistently ✓
- **Arrow keys**: Navigate lists - Works consistently ✓

### Navigation Pattern
- **Enter**: Consistently opens/selects items or dives deeper ✓
- **`b`**: Consistently goes back up the hierarchy ✓
- Hierarchy navigation is logical and predictable ✓

### Note Actions in Main Views
- **`n`**: Add note - Works in case_list, case_detail, evidence_detail ✓
- **Enter on note**: Opens note_detail view - Now consistent across case_detail, evidence_detail, tag_notes_list, ioc_notes_list ✓
- **`v`**: View notes modal with highlight - Now consistent in case_detail and evidence_detail ✓

---

## ❌ INCONSISTENCIES Found

### 1. **'n' Key (Add Note) - Incomplete Coverage** ⚠️
**Issue**: The 'n' key only works in `case_list`, `case_detail`, and `evidence_detail`.

**Missing in**:
- `tags_list` - Pressing 'n' does nothing useful
- `tag_notes_list` - Pressing 'n' does nothing useful
- `ioc_list` - Pressing 'n' does nothing useful
- `ioc_notes_list` - Pressing 'n' does nothing useful
- `note_detail` - Pressing 'n' does nothing useful
- `help` - (OK to not work here)

**Expected behavior**: User should be able to add notes from tag/IOC views since they're actively working with a case/evidence context.

**Recommendation**:
- Make 'n' work in `tag_notes_list` and `ioc_notes_list` by using the parent context (active_case or active_evidence)
- Consider whether it should work in `tags_list` and `ioc_list` as well
- In `note_detail`, 'n' could add a new note to the same context as the currently viewed note

**Code location**: `trace/tui.py:2242` - `dialog_add_note()` only handles 3 views

---

### 2. **'a' Key (Set Active) - Incomplete Implementation** ⚠️
**Issue**: The global handler `key == ord('a')` calls `_handle_set_active()`, but that method only handles:
- `case_list`
- `case_detail`
- `evidence_detail`

**Missing in**:
- `tags_list` - Could set active on the parent case/evidence
- `tag_notes_list` - Silent failure when pressed
- `ioc_list` - Could set active on the parent case/evidence
- `ioc_notes_list` - Silent failure when pressed
- `note_detail` - Silent failure when pressed

**Expected behavior**: Either the key should work (set active on the parent context) or show a message that it's not applicable.

**Recommendation**:
- Option A: Make 'a' work in tag/IOC list views by setting active on the parent case/evidence
- Option B: Show message "Not applicable in this view" when pressed in unsupported views
- Prefer Option A for consistency

**Code location**: `trace/tui.py:1512` - `_handle_set_active()`

---

### 3. **'/' Key (Filter) - Limited Availability** ℹ️
**Issue**: Filter only works in `case_list` and `case_detail`.

**Missing in**:
- `evidence_detail` - Would be useful to filter notes!
- `tags_list` - Would be useful to filter tags
- `tag_notes_list` - Would be useful to filter notes
- `ioc_list` - Would be useful to filter IOCs
- `ioc_notes_list` - Would be useful to filter notes

**Expected behavior**: Users might expect to filter long lists of notes, tags, or IOCs.

**Recommendation**:
- High priority: Add filtering to `evidence_detail` (filter notes by content)
- Medium priority: Add filtering to `tags_list`, `ioc_list` (filter by name/value)
- Lower priority: Add filtering to `tag_notes_list`, `ioc_notes_list` (filter notes by content)

**Code location**: `trace/tui.py:1236-1240` - Filter toggle only checks two views

---

### 4. **'t' and 'i' Keys (Tags/IOCs) - Context-Dependent Availability** ℹ️
**Issue**: These keys only work in `case_detail` and `evidence_detail`.

**Current behavior**: Silent no-op in other views

**Expected behavior**: This is actually reasonable - tags and IOCs are context-specific. However, it might be confusing when users press them in `tag_notes_list` or `ioc_notes_list` and nothing happens.

**Recommendation**:
- Low priority fix: Consider allowing 't' in `ioc_notes_list` to switch to tags view
- Low priority fix: Consider allowing 'i' in `tag_notes_list` to switch to IOCs view
- This would allow quick toggling between tag and IOC exploration
- Alternative: Show helpful message if pressed in unsupported views

**Code location**: `trace/tui.py:1449-1452` - No view restrictions, but handlers at lines 182 and 206 check view

---

### 5. **'d' Key (Delete) - Incomplete Coverage** ⚠️
**Issue**: Delete functionality is not implemented for all views where deletion makes sense.

**Works in**:
- `case_list` - Delete case ✓
- `case_detail` - Delete evidence or note ✓
- `evidence_detail` - Delete note ✓

**Missing in**:
- `tag_notes_list` - Could delete the selected note
- `ioc_notes_list` - Could delete the selected note
- `note_detail` - Could delete the currently viewed note

**Expected behavior**: Users viewing a note should be able to delete it from any view.

**Recommendation**:
- Add delete support for `tag_notes_list` and `ioc_notes_list`
- Add delete support for `note_detail` (delete current note and return to previous view)
- Be careful with confirmation dialogs to prevent accidental deletion

**Code location**: `trace/tui.py:2331` - `handle_delete()` method

---

### 6. **'v' Key (View Notes Modal) - Limited Availability** ℹ️
**Issue**: View notes modal only works in `case_detail` and `evidence_detail`.

**Missing in**:
- `tag_notes_list` - Could show all notes with the tag in a modal
- `ioc_notes_list` - Could show all notes with the IOC in a modal

**Expected behavior**: Might be nice to have a modal view option from tag/IOC note lists, but not critical since they're already list views.

**Recommendation**:
- Low priority: This might be redundant since tag_notes_list and ioc_notes_list are already list views
- Consider if there's a different modal that would be useful (e.g., showing just the tag/IOC highlights)

---

### 7. **'e' Key (Export) - Very Limited** ℹ️
**Issue**: Export only works for IOCs in `ioc_list` and `ioc_notes_list`.

**Missing export options**:
- Export tags from `tags_list`
- Export notes from various views
- Export case summary from `case_detail`

**Expected behavior**: Users might expect export functionality for other data types.

**Recommendation**:
- Medium priority: Add 'e' to export tags from `tags_list`
- Lower priority: Consider export options for notes, cases, evidence

---

## Priority Recommendations

### High Priority (User expects it to work)
1. **Fix 'n' (add note) in tag/IOC note lists** - Users actively working with notes should be able to add new ones
2. **Fix 'a' (set active) to work or give feedback** - Silent failures are confusing
3. **Add filtering to evidence_detail** - Natural extension of existing filter functionality

### Medium Priority (Nice to have)
4. **Add delete support for tag/IOC note lists and note_detail** - Complete the delete functionality
5. **Add filter to tag and IOC lists** - Helpful for large numbers of items
6. **Make 't' and 'i' keys provide feedback** - Better UX than silent failure

### Low Priority (Edge cases)
7. **Cross-navigation between tags and IOCs** - Allow 't' in IOC views and 'i' in tag views
8. **Export tags** - Complement the export IOCs functionality

---

## General Observations

### Strengths
- Core navigation is very consistent (Enter, b, arrows)
- The hierarchy is logical and predictable
- Global keys work well everywhere
- Recent fixes made note navigation consistent ✓

### Areas for Improvement
- Feature keys ('n', 'a', 'd', 't', 'i', 'v') should either work everywhere sensible OR provide clear feedback when not applicable
- Filtering could be more universally available
- Delete functionality should be available wherever items can be viewed
- Silent failures (pressing a key and nothing happening) should be minimized

---

## Testing Recommendations

Create a testing matrix:
- Test each key in each view
- Document expected behavior
- Mark any silent failures
- Ensure error messages are helpful when actions aren't available
