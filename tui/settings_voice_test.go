package main

import (
	"strings"
	"testing"
)

// TestVoiceCursorLineMatchesContent verifies that for every cursor position in
// the Voice section, voiceCursorLine(cursor) points at the rendered SELECTED:
// row in updateSettingsContent. Guards the invariant cm-cjk cares about: if
// the two helpers drift apart the cursor scrolls off-screen.
//
// Extended in cm-y7t: now covers 5 fixed rows (enabled, rate, pitch, volume,
// random) + voice pool + reset, for voicePoolStart + len(voicePool) + 1
// cursor positions.
func TestVoiceCursorLineMatchesContent(t *testing.T) {
	total := voiceSectionCursorCount()
	expected := voicePoolStart + len(voicePool) + 1
	if total != expected {
		t.Fatalf("voiceSectionCursorCount = %d, expected %d", total, expected)
	}

	for cursor := 0; cursor < total; cursor++ {
		m := &model{
			sessionsTab:     "settings",
			settingsSection: settingsSectionVoice,
			settingsCursor:  cursor,
		}
		m.updateSettingsContent()
		line := voiceCursorLine(cursor)
		if line >= len(m.settingsContent) {
			t.Fatalf("cursor=%d: voiceCursorLine=%d out of range (len=%d)", cursor, line, len(m.settingsContent))
		}
		got := m.settingsContent[line]
		if !strings.HasPrefix(got, "SELECTED:") {
			t.Errorf("cursor=%d: content[%d] = %q, expected SELECTED: prefix", cursor, line, got)
		}
	}
}

// TestAdjustVoiceVolume checks the ±5%% stepper math for volume, including
// clamping to [-100, +100] (cm-y7t).
func TestAdjustVoiceVolume(t *testing.T) {
	cases := []struct {
		in    string
		delta int
		want  string
	}{
		{"+0%", 5, "+5%"},
		{"+0%", -5, "-5%"},
		{"-100%", -5, "-100%"}, // clamp
		{"+100%", 5, "+100%"},  // clamp
		{"-20%", 5, "-15%"},
		{"+20%", -5, "+15%"},
	}
	for _, c := range cases {
		got := adjustVoiceVolumePercent(c.in, c.delta)
		if got != c.want {
			t.Errorf("adjustVoiceVolumePercent(%q,%d) = %q, want %q", c.in, c.delta, got, c.want)
		}
	}
}

// TestAdjustVoiceRate checks the ±5%% stepper math, including clamping.
func TestAdjustVoiceRate(t *testing.T) {
	cases := []struct {
		in    string
		delta int
		want  string
	}{
		{"+20%", 5, "+25%"},
		{"+20%", -5, "+15%"},
		{"+0%", -5, "-5%"},
		{"-100%", -5, "-100%"}, // clamp
		{"+300%", 5, "+300%"},  // clamp
		{"+15%", 10, "+25%"},
		{"garbage", 5, "+5%"}, // falls back to 0 then +5
	}
	for _, c := range cases {
		got := adjustVoiceRatePercent(c.in, c.delta)
		if got != c.want {
			t.Errorf("adjustVoiceRatePercent(%q,%d) = %q, want %q", c.in, c.delta, got, c.want)
		}
	}
}

// TestAdjustVoicePitch checks the ±5Hz stepper math.
func TestAdjustVoicePitch(t *testing.T) {
	cases := []struct {
		in    string
		delta int
		want  string
	}{
		{"+0Hz", 5, "+5Hz"},
		{"+0Hz", -5, "-5Hz"},
		{"+200Hz", 5, "+200Hz"},   // clamp
		{"-200Hz", -5, "-200Hz"},  // clamp
		{"-10Hz", 5, "-5Hz"},
	}
	for _, c := range cases {
		got := adjustVoicePitchHz(c.in, c.delta)
		if got != c.want {
			t.Errorf("adjustVoicePitchHz(%q,%d) = %q, want %q", c.in, c.delta, got, c.want)
		}
	}
}
