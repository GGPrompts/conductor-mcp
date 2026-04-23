package main

import (
	"fmt"
	"os/exec"
	"strings"
)

// settings.go - Settings Panel (cm-3gw)
//
// Exposes a Settings tab in the top panel (cycle via panel-1 key, alongside
// Sessions and Templates). MVP covers the Voice section — pick a voice from
// the pool, test it end-to-end by shelling out to edge-tts + mpv, and persist
// the choice to the canonical config (~/.config/conductor/config.json).
//
// Additional sections (Profiles CRUD, Layout/Timing) are stubbed in-view so
// users see what's planned. Full CRUD for those lands in a follow-up (see retro).

// The embedded voice pool mirrors VOICE_POOL in server.py. Kept in sync by
// convention — if the pool drifts, a future refactor should pull it from the
// canonical config too.
var voicePool = []string{
	"en-US-AriaNeural",
	"en-US-GuyNeural",
	"en-US-JennyNeural",
	"en-US-DavisNeural",
	"en-US-AmberNeural",
	"en-US-AndrewNeural",
	"en-US-EmmaNeural",
	"en-US-BrianNeural",
	"en-US-AnaNeural",
	"en-US-ChristopherNeural",
	"en-GB-SoniaNeural",
	"en-GB-RyanNeural",
	"en-AU-NatashaNeural",
	"en-AU-WilliamNeural",
}

// settingsSection identifiers shown in the panel.
const (
	settingsSectionVoice   = "voice"
	settingsSectionProfile = "profiles"
	settingsSectionTiming  = "timing"
)

// settingsGetVoice reads the current default voice from the canonical config.
func settingsGetVoice() string {
	root := loadCanonicalRoot()
	if voice, ok := root["voice"].(map[string]interface{}); ok {
		if d, ok := voice["default"].(string); ok && d != "" {
			return d
		}
	}
	// Fallback to audio section if present (cm-d64 schema)
	if audio, ok := root["audio"].(map[string]interface{}); ok {
		if d, ok := audio["default_voice"].(string); ok && d != "" {
			return d
		}
	}
	return "en-US-AndrewNeural"
}

// settingsGetVoiceRate returns the current voice rate.
func settingsGetVoiceRate() string {
	root := loadCanonicalRoot()
	if voice, ok := root["voice"].(map[string]interface{}); ok {
		if r, ok := voice["rate"].(string); ok && r != "" {
			return r
		}
	}
	if audio, ok := root["audio"].(map[string]interface{}); ok {
		if r, ok := audio["voice_rate"].(string); ok && r != "" {
			return r
		}
	}
	return "+20%"
}

// settingsGetVoicePitch returns the current voice pitch.
func settingsGetVoicePitch() string {
	root := loadCanonicalRoot()
	if voice, ok := root["voice"].(map[string]interface{}); ok {
		if p, ok := voice["pitch"].(string); ok && p != "" {
			return p
		}
	}
	if audio, ok := root["audio"].(map[string]interface{}); ok {
		if p, ok := audio["voice_pitch"].(string); ok && p != "" {
			return p
		}
	}
	return "+0Hz"
}

// settingsGetRandomPerWorker returns the current random_per_worker toggle.
// Defaults to true to match server.py's DEFAULT_CONFIG (cm-06j).
func settingsGetRandomPerWorker() bool {
	root := loadCanonicalRoot()
	if voice, ok := root["voice"].(map[string]interface{}); ok {
		if b, ok := voice["random_per_worker"].(bool); ok {
			return b
		}
	}
	return true
}

// settingsSaveVoice persists the default voice to the canonical config.
// Writes under "voice" to match the current MCP server schema; a future
// cm-2k1 iteration may rename to "audio" per cm-d64's final schema.
func settingsSaveVoice(voice string) error {
	root := loadCanonicalRoot()
	if root == nil {
		root = map[string]interface{}{}
	}
	v, _ := root["voice"].(map[string]interface{})
	if v == nil {
		v = map[string]interface{}{}
	}
	v["default"] = voice
	root["voice"] = v
	return saveCanonicalRoot(root)
}

// settingsSaveVoiceRate persists voice.rate to the canonical config. The value
// should be a string in edge-tts' expected "+XX%" / "-XX%" form (cm-06j).
func settingsSaveVoiceRate(rate string) error {
	root := loadCanonicalRoot()
	if root == nil {
		root = map[string]interface{}{}
	}
	v, _ := root["voice"].(map[string]interface{})
	if v == nil {
		v = map[string]interface{}{}
	}
	v["rate"] = rate
	root["voice"] = v
	return saveCanonicalRoot(root)
}

// settingsSaveVoicePitch persists voice.pitch to the canonical config. The
// value should be in edge-tts' "+YYHz" / "-YYHz" form (cm-06j).
func settingsSaveVoicePitch(pitch string) error {
	root := loadCanonicalRoot()
	if root == nil {
		root = map[string]interface{}{}
	}
	v, _ := root["voice"].(map[string]interface{})
	if v == nil {
		v = map[string]interface{}{}
	}
	v["pitch"] = pitch
	root["voice"] = v
	return saveCanonicalRoot(root)
}

// settingsSaveRandomPerWorker persists voice.random_per_worker. Keeps the
// current key name — do not reintroduce the legacy "random_voices" key
// (cm-06j, cm-3gw).
func settingsSaveRandomPerWorker(val bool) error {
	root := loadCanonicalRoot()
	if root == nil {
		root = map[string]interface{}{}
	}
	v, _ := root["voice"].(map[string]interface{})
	if v == nil {
		v = map[string]interface{}{}
	}
	v["random_per_worker"] = val
	root["voice"] = v
	return saveCanonicalRoot(root)
}

// settingsResetVoiceAssignments clears the worker_voice_assignments map and
// resets voice_pool_index in the canonical config. Mirrors the removed
// reset_voice_assignments MCP tool (cm-06j / cm-3gw).
func settingsResetVoiceAssignments() error {
	root := loadCanonicalRoot()
	if root == nil {
		root = map[string]interface{}{}
	}
	root["worker_voice_assignments"] = map[string]interface{}{}
	root["voice_pool_index"] = float64(0)
	return saveCanonicalRoot(root)
}

// settingsCountVoiceAssignments returns how many workers have pinned voices,
// used to render the Reset action row (cm-06j).
func settingsCountVoiceAssignments() int {
	root := loadCanonicalRoot()
	if m, ok := root["worker_voice_assignments"].(map[string]interface{}); ok {
		return len(m)
	}
	return 0
}

// adjustVoiceRatePercent returns rate + deltaPct, clamped to [-100, +300].
// Input format matches edge-tts: "+XX%" or "-XX%". Non-numeric input falls
// back to +0% (cm-06j).
func adjustVoiceRatePercent(rate string, deltaPct int) string {
	n := parseSignedNumber(rate, "%")
	n += deltaPct
	if n < -100 {
		n = -100
	}
	if n > 300 {
		n = 300
	}
	return formatSigned(n) + "%"
}

// adjustVoicePitchHz returns pitch + deltaHz, clamped to [-200, +200]. Input
// format matches edge-tts: "+YYHz" or "-YYHz" (cm-06j).
func adjustVoicePitchHz(pitch string, deltaHz int) string {
	n := parseSignedNumber(pitch, "Hz")
	n += deltaHz
	if n < -200 {
		n = -200
	}
	if n > 200 {
		n = 200
	}
	return formatSigned(n) + "Hz"
}

// parseSignedNumber strips an optional sign and a trailing unit suffix, then
// parses the remaining integer. Returns 0 if parsing fails.
func parseSignedNumber(s, unit string) int {
	s = strings.TrimSpace(s)
	s = strings.TrimSuffix(s, unit)
	s = strings.TrimSpace(s)
	if s == "" {
		return 0
	}
	sign := 1
	switch s[0] {
	case '+':
		s = s[1:]
	case '-':
		sign = -1
		s = s[1:]
	}
	var n int
	if _, err := fmt.Sscanf(s, "%d", &n); err != nil {
		return 0
	}
	return sign * n
}

// formatSigned renders an integer with a leading sign so edge-tts accepts it.
func formatSigned(n int) string {
	if n >= 0 {
		return fmt.Sprintf("+%d", n)
	}
	return fmt.Sprintf("%d", n)
}

// cursorMarker returns the 2-char gutter shown in front of a Settings row,
// "► " when the cursor is on that row and "  " otherwise.
func cursorMarker(selected bool) string {
	if selected {
		return "► "
	}
	return "  "
}

// testVoice shells out to edge-tts + mpv to preview a voice.
// Matches server.py's speak() invocation pattern: generate to a tempfile,
// then play with mpv. Does not require the MCP server.
func testVoice(voice, rate, text string) error {
	if text == "" {
		text = "Hello, I am your conductor assistant."
	}
	if rate == "" {
		rate = "+20%"
	}
	// Write to a temp mp3 so mpv has a concrete file.
	tmp := fmt.Sprintf("/tmp/conductor-tui-voice-test-%d.mp3", 0)

	// Generate audio
	gen := exec.Command(
		"edge-tts",
		"--voice", voice,
		"--rate", rate,
		"--text", text,
		"--write-media", tmp,
	)
	if out, err := gen.CombinedOutput(); err != nil {
		return fmt.Errorf("edge-tts failed: %v (%s)", err, strings.TrimSpace(string(out)))
	}

	// Play (try mpv, then ffplay, then cvlc)
	for _, attempt := range [][]string{
		{"mpv", "--no-video", "--really-quiet", tmp},
		{"ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp},
		{"cvlc", "--play-and-exit", "--quiet", tmp},
	} {
		c := exec.Command(attempt[0], attempt[1:]...)
		if err := c.Run(); err == nil {
			return nil
		}
	}
	return fmt.Errorf("no audio player found (install mpv, ffplay, or vlc)")
}

// listProfiles returns profiles from the canonical config.
func settingsListProfiles() []string {
	root := loadCanonicalRoot()
	profiles, ok := root["profiles"].(map[string]interface{})
	if !ok {
		return nil
	}
	names := make([]string, 0, len(profiles))
	for k := range profiles {
		names = append(names, k)
	}
	return names
}
