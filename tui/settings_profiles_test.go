package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// writeTempConfig sets HOME to a tempdir and writes a canonical config with
// the given top-level JSON. Returns the tempdir (caller restores HOME via
// t.Cleanup).
func writeTempConfig(t *testing.T, root map[string]interface{}) string {
	t.Helper()
	home := t.TempDir()
	t.Setenv("HOME", home)
	dir := filepath.Join(home, ".config", "conductor")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	data, err := json.MarshalIndent(root, "", "  ")
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "config.json"), data, 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	return home
}

// TestProfileCursorLineMatchesContent verifies that for every cursor position
// in the Profiles section, profileCursorLine points at the rendered SELECTED:
// row in updateSettingsContent. Guards the same invariant Voice tests do
// (cm-cjk): drift between the helper and the renderer scrolls cursor
// off-screen (cm-b6r).
func TestProfileCursorLineMatchesContent(t *testing.T) {
	// Seed a config with three profiles so we exercise >1 cursor row plus the
	// "+ Add profile" row.
	writeTempConfig(t, map[string]interface{}{
		"profiles": map[string]interface{}{
			"claude": map[string]interface{}{"command": "claude", "description": "Default"},
			"codex":  map[string]interface{}{"command": "codex", "description": "OpenAI"},
			"gemini": map[string]interface{}{"command": "gemini -i", "description": "Google"},
		},
	})

	total := profilesSectionCursorCount()
	if total != 4 {
		t.Fatalf("profilesSectionCursorCount = %d, expected 4 (3 profiles + add)", total)
	}

	for cursor := 0; cursor < total; cursor++ {
		m := &model{
			sessionsTab:     "settings",
			settingsSection: settingsSectionProfile,
			settingsCursor:  cursor,
		}
		m.updateSettingsContent()
		line := profileCursorLine(cursor)
		if line >= len(m.settingsContent) {
			t.Fatalf("cursor=%d: profileCursorLine=%d out of range (len=%d)", cursor, line, len(m.settingsContent))
		}
		got := m.settingsContent[line]
		if !strings.HasPrefix(got, "SELECTED:") {
			t.Errorf("cursor=%d: content[%d] = %q, expected SELECTED: prefix", cursor, line, got)
		}
	}
}

// TestProfileCursorLineEmpty verifies the empty-profile case still lands on
// the "+ Add profile" row.
func TestProfileCursorLineEmpty(t *testing.T) {
	writeTempConfig(t, map[string]interface{}{
		"profiles": map[string]interface{}{},
	})

	total := profilesSectionCursorCount()
	if total != 1 {
		t.Fatalf("profilesSectionCursorCount = %d, expected 1 (add only)", total)
	}

	m := &model{
		sessionsTab:     "settings",
		settingsSection: settingsSectionProfile,
		settingsCursor:  0,
	}
	m.updateSettingsContent()
	line := profileCursorLine(0)
	if line >= len(m.settingsContent) {
		t.Fatalf("profileCursorLine(0) = %d out of range (len=%d)", line, len(m.settingsContent))
	}
	got := m.settingsContent[line]
	if !strings.HasPrefix(got, "SELECTED:") {
		t.Errorf("content[%d] = %q, expected SELECTED: prefix", line, got)
	}
	if !strings.Contains(got, "+ Add profile") {
		t.Errorf("content[%d] = %q, expected to contain \"+ Add profile\"", line, got)
	}
}

// TestTimingCursorLineMatchesContent verifies that for every cursor position
// in the Timing section, timingCursorLine points at the rendered SELECTED:
// row (cm-b6r).
func TestTimingCursorLineMatchesContent(t *testing.T) {
	writeTempConfig(t, map[string]interface{}{
		"default_layout": "2x2",
		"default_dir":    "~",
		"delays": map[string]interface{}{
			"send_keys_ms":   float64(800),
			"claude_boot_s":  float64(4),
		},
	})

	total := timingSectionCursorCount()
	if total != 4 {
		t.Fatalf("timingSectionCursorCount = %d, expected 4", total)
	}

	for cursor := 0; cursor < total; cursor++ {
		m := &model{
			sessionsTab:     "settings",
			settingsSection: settingsSectionTiming,
			settingsCursor:  cursor,
		}
		m.updateSettingsContent()
		line := timingCursorLine(cursor)
		if line >= len(m.settingsContent) {
			t.Fatalf("cursor=%d: timingCursorLine=%d out of range (len=%d)", cursor, line, len(m.settingsContent))
		}
		got := m.settingsContent[line]
		if !strings.HasPrefix(got, "SELECTED:") {
			t.Errorf("cursor=%d: content[%d] = %q, expected SELECTED: prefix", cursor, line, got)
		}
	}
}

// TestSaveTimingFieldValidation exercises the validators for default_layout,
// default_dir, send_keys_ms, and claude_boot_s (cm-b6r).
func TestSaveTimingFieldValidation(t *testing.T) {
	writeTempConfig(t, map[string]interface{}{})

	cases := []struct {
		field   string
		value   string
		wantErr bool
	}{
		{"default_layout", "2x2", false},
		{"default_layout", "3x4", false},
		{"default_layout", "0x2", true},
		{"default_layout", "2x", true},
		{"default_layout", "abc", true},
		{"default_layout", "", true},
		{"default_dir", "~", false},
		{"default_dir", "/home/foo", false},
		{"default_dir", "", true},
		{"default_dir", "   ", true}, // trimmed to empty
		{"send_keys_ms", "800", false},
		{"send_keys_ms", "0", false},
		{"send_keys_ms", "-1", true},
		{"send_keys_ms", "abc", true},
		{"send_keys_ms", "", true},
		{"claude_boot_s", "4", false},
		{"claude_boot_s", "0", false},
		{"claude_boot_s", "-5", true},
		{"claude_boot_s", "1.5", true},
		{"bogus_field", "whatever", true},
	}
	for _, c := range cases {
		err := settingsSaveTimingField(c.field, c.value)
		if (err != nil) != c.wantErr {
			t.Errorf("settingsSaveTimingField(%q,%q) err=%v wantErr=%v", c.field, c.value, err, c.wantErr)
		}
	}
}

// TestProfileCRUDRoundtrip exercises save → list → rename → delete end-to-end
// on a freshly initialized config.json (cm-b6r).
func TestProfileCRUDRoundtrip(t *testing.T) {
	writeTempConfig(t, map[string]interface{}{})

	// Create
	if err := settingsSaveProfile("foo", "run-foo", "does foo"); err != nil {
		t.Fatalf("save foo: %v", err)
	}
	if err := settingsSaveProfile("bar", "run-bar", ""); err != nil {
		t.Fatalf("save bar: %v", err)
	}
	names := settingsListProfiles()
	if len(names) != 2 || names[0] != "bar" || names[1] != "foo" {
		t.Fatalf("expected sorted [bar foo], got %v", names)
	}

	// Read
	cmd, desc := settingsGetProfile("foo")
	if cmd != "run-foo" || desc != "does foo" {
		t.Errorf("get foo = (%q,%q), want (run-foo,does foo)", cmd, desc)
	}

	// Rename
	if err := settingsRenameProfile("foo", "foo2"); err != nil {
		t.Fatalf("rename: %v", err)
	}
	names = settingsListProfiles()
	if len(names) != 2 || names[0] != "bar" || names[1] != "foo2" {
		t.Fatalf("expected [bar foo2] after rename, got %v", names)
	}
	// Rename onto an existing name should fail.
	if err := settingsRenameProfile("foo2", "bar"); err == nil {
		t.Error("rename into existing name should fail")
	}

	// Delete
	if err := settingsDeleteProfile("bar"); err != nil {
		t.Fatalf("delete bar: %v", err)
	}
	names = settingsListProfiles()
	if len(names) != 1 || names[0] != "foo2" {
		t.Fatalf("expected [foo2] after delete, got %v", names)
	}
	// Deleting a missing profile is a no-op.
	if err := settingsDeleteProfile("nonexistent"); err != nil {
		t.Errorf("delete nonexistent should be no-op, got %v", err)
	}
}
