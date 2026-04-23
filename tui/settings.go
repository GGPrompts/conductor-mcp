package main

import (
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"sort"
	"strconv"
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

// settingsGetVoiceVolume returns the current voice volume. Mirrors
// voice.rate/pitch getters — edge-tts expects "+XX%" form (cm-y7t).
func settingsGetVoiceVolume() string {
	root := loadCanonicalRoot()
	if voice, ok := root["voice"].(map[string]interface{}); ok {
		if v, ok := voice["volume"].(string); ok && v != "" {
			return v
		}
	}
	return "+0%"
}

// settingsGetVoiceEnabled returns the canonical audio on/off toggle. Gates
// both MCP speak() and state-tracker chimes (cm-y7t). Default is true to
// match server.py DEFAULT_CONFIG.
func settingsGetVoiceEnabled() bool {
	root := loadCanonicalRoot()
	if voice, ok := root["voice"].(map[string]interface{}); ok {
		if b, ok := voice["enabled"].(bool); ok {
			return b
		}
	}
	return true
}

// saveVoiceKey is the shared load-mutate-save helper for the root["voice"]
// section. All settingsSaveVoice* callers delegate here so there's one place
// to update if the schema shifts (cm-d64, cm-06j).
func saveVoiceKey(key string, value interface{}) error {
	root := loadCanonicalRoot()
	if root == nil {
		root = map[string]interface{}{}
	}
	v, _ := root["voice"].(map[string]interface{})
	if v == nil {
		v = map[string]interface{}{}
	}
	v[key] = value
	root["voice"] = v
	return saveCanonicalRoot(root)
}

// settingsSaveVoice persists the default voice to the canonical config.
// Writes under "voice" to match the current MCP server schema; a future
// cm-2k1 iteration may rename to "audio" per cm-d64's final schema.
func settingsSaveVoice(voice string) error {
	return saveVoiceKey("default", voice)
}

// settingsSaveVoiceRate persists voice.rate to the canonical config. The value
// should be a string in edge-tts' expected "+XX%" / "-XX%" form (cm-06j).
func settingsSaveVoiceRate(rate string) error {
	return saveVoiceKey("rate", rate)
}

// settingsSaveVoicePitch persists voice.pitch to the canonical config. The
// value should be in edge-tts' "+YYHz" / "-YYHz" form (cm-06j).
func settingsSaveVoicePitch(pitch string) error {
	return saveVoiceKey("pitch", pitch)
}

// settingsSaveRandomPerWorker persists voice.random_per_worker. Keeps the
// current key name — do not reintroduce the legacy "random_voices" key
// (cm-06j, cm-3gw).
func settingsSaveRandomPerWorker(val bool) error {
	return saveVoiceKey("random_per_worker", val)
}

// settingsSaveVoiceVolume persists voice.volume. edge-tts expects "+XX%"
// form (cm-y7t).
func settingsSaveVoiceVolume(volume string) error {
	return saveVoiceKey("volume", volume)
}

// settingsSaveVoiceEnabled persists the canonical audio on/off toggle
// (cm-y7t).
func settingsSaveVoiceEnabled(val bool) error {
	return saveVoiceKey("enabled", val)
}

// adjustVoiceVolumePercent returns volume + deltaPct, clamped to [-100,
// +100]. edge-tts accepts "+XX%" / "-XX%" — mirrors the rate stepper UX
// (cm-y7t).
func adjustVoiceVolumePercent(volume string, deltaPct int) string {
	n := parseSignedNumber(volume, "%")
	n += deltaPct
	if n < -100 {
		n = -100
	}
	if n > 100 {
		n = 100
	}
	return formatSigned(n) + "%"
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
// then play with mpv. Does not require the MCP server. Reads pitch +
// volume from canonical config so previews match production output
// (cm-y7t).
func testVoice(voice, rate, text string) error {
	if text == "" {
		text = "Hello, I am your conductor assistant."
	}
	if rate == "" {
		rate = "+20%"
	}
	pitch := settingsGetVoicePitch()
	volume := settingsGetVoiceVolume()
	// Write to a unique temp mp3 so mpv has a concrete file. Using
	// os.CreateTemp avoids a predictable-path symlink attack and prevents
	// concurrent-call collisions between overlapping previews.
	f, err := os.CreateTemp("", "conductor-tui-voice-test-*.mp3")
	if err != nil {
		return fmt.Errorf("create temp file: %v", err)
	}
	tmp := f.Name()
	_ = f.Close()
	defer os.Remove(tmp)

	// Generate audio
	gen := exec.Command(
		"edge-tts",
		"--voice", voice,
		"--rate", rate,
		"--pitch", pitch,
		"--volume", volume,
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

// listProfiles returns profile names sorted alphabetically. Sorted output keeps
// the cursor row stable across reloads (cm-b6r).
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
	sort.Strings(names)
	return names
}

// settingsGetProfile returns the (command, description) pair for a named
// profile, or empty strings if it does not exist (cm-b6r).
func settingsGetProfile(name string) (command, description string) {
	root := loadCanonicalRoot()
	profiles, _ := root["profiles"].(map[string]interface{})
	if profiles == nil {
		return "", ""
	}
	entry, _ := profiles[name].(map[string]interface{})
	if entry == nil {
		return "", ""
	}
	if c, ok := entry["command"].(string); ok {
		command = c
	}
	if d, ok := entry["description"].(string); ok {
		description = d
	}
	return command, description
}

// settingsSaveProfile creates or updates a profile entry in the canonical
// config. Missing fields are stored as empty strings (stub-friendly) (cm-b6r).
func settingsSaveProfile(name, command, description string) error {
	root := loadCanonicalRoot()
	if root == nil {
		root = map[string]interface{}{}
	}
	profiles, _ := root["profiles"].(map[string]interface{})
	if profiles == nil {
		profiles = map[string]interface{}{}
	}
	entry, _ := profiles[name].(map[string]interface{})
	if entry == nil {
		entry = map[string]interface{}{}
	}
	entry["command"] = command
	entry["description"] = description
	profiles[name] = entry
	root["profiles"] = profiles
	return saveCanonicalRoot(root)
}

// settingsDeleteProfile removes a profile from the canonical config. Returns
// nil if the profile didn't exist (idempotent) (cm-b6r).
func settingsDeleteProfile(name string) error {
	root := loadCanonicalRoot()
	if root == nil {
		return nil
	}
	profiles, _ := root["profiles"].(map[string]interface{})
	if profiles == nil {
		return nil
	}
	delete(profiles, name)
	root["profiles"] = profiles
	return saveCanonicalRoot(root)
}

// settingsRenameProfile renames a profile, preserving command/description.
// No-op if oldName == newName. Errors if newName already exists (cm-b6r).
func settingsRenameProfile(oldName, newName string) error {
	if oldName == newName {
		return nil
	}
	if newName == "" {
		return fmt.Errorf("profile name cannot be empty")
	}
	root := loadCanonicalRoot()
	if root == nil {
		return fmt.Errorf("profile %q not found", oldName)
	}
	profiles, _ := root["profiles"].(map[string]interface{})
	if profiles == nil {
		return fmt.Errorf("profile %q not found", oldName)
	}
	if _, exists := profiles[newName]; exists {
		return fmt.Errorf("profile %q already exists", newName)
	}
	entry, ok := profiles[oldName]
	if !ok {
		return fmt.Errorf("profile %q not found", oldName)
	}
	profiles[newName] = entry
	delete(profiles, oldName)
	root["profiles"] = profiles
	return saveCanonicalRoot(root)
}

// Timing section helpers. All values live at the canonical top level:
//   default_layout: string like "2x2"
//   default_dir:    string (home-relative ok)
//   delays.send_keys_ms: integer
//   delays.claude_boot_s: integer

const (
	timingDefaultLayout = "2x2"
	timingDefaultDir    = "~"
	timingDefaultSendMs = 800
	timingDefaultBootS  = 4
)

// settingsGetTiming returns all four timing values with defaults (cm-b6r).
func settingsGetTiming() (layout, dir string, sendKeysMs, claudeBootS int) {
	root := loadCanonicalRoot()
	layout = timingDefaultLayout
	dir = timingDefaultDir
	sendKeysMs = timingDefaultSendMs
	claudeBootS = timingDefaultBootS
	if s, ok := root["default_layout"].(string); ok && s != "" {
		layout = s
	}
	if s, ok := root["default_dir"].(string); ok && s != "" {
		dir = s
	}
	if d, ok := root["delays"].(map[string]interface{}); ok {
		if v, ok := d["send_keys_ms"].(float64); ok {
			sendKeysMs = int(v)
		}
		if v, ok := d["claude_boot_s"].(float64); ok {
			claudeBootS = int(v)
		}
	}
	return layout, dir, sendKeysMs, claudeBootS
}

// layoutPattern enforces the Nx M grid form for default_layout (cm-b6r).
var layoutPattern = regexp.MustCompile(`^[1-9]x[1-9]$`)

// settingsSaveTimingField validates and persists a single timing field. The
// field key is one of: "default_layout", "default_dir", "send_keys_ms",
// "claude_boot_s" (cm-b6r).
func settingsSaveTimingField(field, value string) error {
	value = strings.TrimSpace(value)
	root := loadCanonicalRoot()
	if root == nil {
		root = map[string]interface{}{}
	}
	switch field {
	case "default_layout":
		if !layoutPattern.MatchString(value) {
			return fmt.Errorf("layout must match NxM (e.g. 2x2), got %q", value)
		}
		root["default_layout"] = value
	case "default_dir":
		if value == "" {
			return fmt.Errorf("default_dir cannot be empty")
		}
		root["default_dir"] = value
	case "send_keys_ms":
		n, err := strconv.Atoi(value)
		if err != nil || n < 0 {
			return fmt.Errorf("send_keys_ms must be a non-negative integer, got %q", value)
		}
		delays, _ := root["delays"].(map[string]interface{})
		if delays == nil {
			delays = map[string]interface{}{}
		}
		delays["send_keys_ms"] = float64(n)
		root["delays"] = delays
	case "claude_boot_s":
		n, err := strconv.Atoi(value)
		if err != nil || n < 0 {
			return fmt.Errorf("claude_boot_s must be a non-negative integer, got %q", value)
		}
		delays, _ := root["delays"].(map[string]interface{})
		if delays == nil {
			delays = map[string]interface{}{}
		}
		delays["claude_boot_s"] = float64(n)
		root["delays"] = delays
	default:
		return fmt.Errorf("unknown timing field %q", field)
	}
	return saveCanonicalRoot(root)
}

// timingFieldOrder is the canonical cursor order for the Timing section.
// Cursor index maps directly to this slice (cm-b6r).
var timingFieldOrder = []string{
	"default_layout",
	"default_dir",
	"send_keys_ms",
	"claude_boot_s",
}

// timingFieldValueStr returns the current field value as a display string.
func timingFieldValueStr(field string) string {
	layout, dir, sendMs, bootS := settingsGetTiming()
	switch field {
	case "default_layout":
		return layout
	case "default_dir":
		return dir
	case "send_keys_ms":
		return strconv.Itoa(sendMs)
	case "claude_boot_s":
		return strconv.Itoa(bootS)
	}
	return ""
}
