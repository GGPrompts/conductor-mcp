package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// config.go - Configuration Management
// Purpose: Load and manage application configuration
//
// Canonical config: ~/.config/conductor/config.json (cm-d64 decision).
// Shared with the conductor MCP server — both components read/write the same file.
// The TUI owns the "tui" section; MCP server owns "mcp", "audio" (voice), "profiles",
// "voices" (runtime). Other sections are preserved round-trip when saving.

// loadConfig loads configuration from file or returns defaults
func loadConfig() Config {
	// Try to load from canonical config file (migrating from legacy paths if needed)
	cfg, err := loadConfigFile()
	if err != nil {
		// Return default config if load fails
		return getDefaultConfig()
	}

	// Apply custom theme if specified
	if cfg.Theme == "custom" && cfg.CustomTheme.Primary != "" {
		applyTheme(cfg.CustomTheme)
	}

	return cfg
}

// loadConfigFile loads configuration from the canonical JSON file, migrating from
// the legacy YAML path on first run.
func loadConfigFile() (Config, error) {
	configPath := getConfigPath()

	// Canonical file exists — read JSON
	if _, statErr := os.Stat(configPath); statErr == nil {
		data, err := os.ReadFile(configPath)
		if err != nil {
			return Config{}, err
		}
		return parseCanonicalJSON(data)
	}

	// Canonical absent — attempt migration from legacy YAML (conductor-tui/config.yaml)
	legacyPath := getLegacyTUIConfigPath()
	if _, statErr := os.Stat(legacyPath); statErr == nil {
		data, err := os.ReadFile(legacyPath)
		if err == nil {
			var cfg Config
			if yamlErr := yaml.Unmarshal(data, &cfg); yamlErr == nil {
				cfg = applyDefaults(cfg)
				// Persist into canonical JSON (best-effort)
				_ = saveConfig(cfg)
				return cfg, nil
			}
		}
	}

	// Nothing to load — return an error so the caller falls back to defaults
	return Config{}, os.ErrNotExist
}

// parseCanonicalJSON extracts the "tui" section (or root-level compatible shape)
// out of the canonical config file into the TUI's Config struct. Missing fields
// fall back to defaults.
func parseCanonicalJSON(data []byte) (Config, error) {
	var root map[string]json.RawMessage
	if err := json.Unmarshal(data, &root); err != nil {
		return Config{}, err
	}

	// Prefer the "tui" section; fall back to root if the file is in pre-migration shape.
	var cfg Config
	if tuiRaw, ok := root["tui"]; ok {
		_ = json.Unmarshal(tuiRaw, &cfg)
	}

	cfg = applyDefaults(cfg)
	return cfg, nil
}

// getDefaultConfig returns the default configuration
func getDefaultConfig() Config {
	return Config{
		Theme: "dark",
		CustomTheme: ThemeColors{
			Primary:    "#61AFEF",
			Secondary:  "#C678DD",
			Background: "#282C34",
			Foreground: "#ABB2BF",
			Accent:     "#98C379",
			Error:      "#E06C75",
		},
		Keybindings: "default",
		CustomKeybindings: map[string]string{
			"quit":    "q",
			"help":    "?",
			"refresh": "ctrl+r",
		},
		Layout: LayoutConfig{
			Type:        "single",
			SplitRatio:  0.5,
			ShowDivider: true,
		},
		UI: UIConfig{
			ShowTitle:       true,
			ShowStatus:      true,
			ShowLineNumbers: false,
			MouseEnabled:    true,
			ShowIcons:       true,
			IconSet:         "nerd_font",
		},
		Performance: PerformanceConfig{
			LazyLoading:     true,
			CacheSize:       100,
			AsyncOperations: true,
		},
		Logging: LogConfig{
			Enabled: false,
			Level:   "info",
			File:    getDefaultLogPath(),
		},
	}
}

// applyDefaults fills in missing fields with default values
func applyDefaults(cfg Config) Config {
	defaults := getDefaultConfig()

	// Apply defaults for zero values
	if cfg.Theme == "" {
		cfg.Theme = defaults.Theme
	}
	if cfg.Keybindings == "" {
		cfg.Keybindings = defaults.Keybindings
	}
	if cfg.Layout.Type == "" {
		cfg.Layout = defaults.Layout
	}
	if cfg.Layout.SplitRatio == 0 {
		cfg.Layout.SplitRatio = defaults.Layout.SplitRatio
	}

	// UI defaults
	if !cfg.UI.MouseEnabled && !cfg.UI.ShowTitle && !cfg.UI.ShowStatus {
		cfg.UI = defaults.UI
	}

	// Performance defaults
	if cfg.Performance.CacheSize == 0 {
		cfg.Performance.CacheSize = defaults.Performance.CacheSize
	}

	// Logging defaults
	if cfg.Logging.File == "" {
		cfg.Logging.File = defaults.Logging.File
	}
	if cfg.Logging.Level == "" {
		cfg.Logging.Level = defaults.Logging.Level
	}

	return cfg
}

// saveConfig saves the current configuration to the canonical JSON file.
// It preserves unknown top-level sections (mcp, audio, profiles, voices) so the
// TUI doesn't stomp MCP-owned state.
func saveConfig(cfg Config) error {
	configPath := getConfigPath()
	if configPath == "" {
		return fmt.Errorf("cannot determine config path: home directory unavailable")
	}

	// Create config directory if it doesn't exist
	configDir := filepath.Dir(configPath)
	if err := os.MkdirAll(configDir, 0755); err != nil {
		return err
	}

	// Read existing root (if any) to preserve sibling sections
	root := map[string]interface{}{}
	if existing, err := os.ReadFile(configPath); err == nil {
		_ = json.Unmarshal(existing, &root)
	}

	// Overwrite our owned section
	root["tui"] = cfg

	data, err := json.MarshalIndent(root, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(configPath, data, 0600)
}

// loadCanonicalRoot returns the full canonical config as a generic map.
// Used by the Settings panel to read sections (audio/voice, profiles, mcp) that
// the TUI displays but doesn't parse into a typed struct.
func loadCanonicalRoot() map[string]interface{} {
	configPath := getConfigPath()
	if configPath == "" {
		// Home directory unavailable — avoid reading an arbitrary file from
		// CWD by refusing to proceed. Callers treat an empty map as "no
		// config yet", which is the safe fallback here.
		return map[string]interface{}{}
	}
	data, err := os.ReadFile(configPath)
	if err != nil {
		return map[string]interface{}{}
	}
	var root map[string]interface{}
	if err := json.Unmarshal(data, &root); err != nil {
		return map[string]interface{}{}
	}
	return root
}

// saveCanonicalRoot writes a full canonical config map, used by Settings panel
// when mutating non-TUI sections.
func saveCanonicalRoot(root map[string]interface{}) error {
	configPath := getConfigPath()
	if configPath == "" {
		return fmt.Errorf("cannot determine config path: home directory unavailable")
	}
	configDir := filepath.Dir(configPath)
	if err := os.MkdirAll(configDir, 0755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(root, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(configPath, data, 0600)
}

// getConfigPath returns the path to the canonical config file
func getConfigPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}

	return filepath.Join(home, ".config", "conductor", "config.json")
}

// getLegacyTUIConfigPath returns the old YAML TUI config path (for migration only)
func getLegacyTUIConfigPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}

	return filepath.Join(home, ".config", "conductor-tui", "config.yaml")
}

// getDefaultLogPath returns the default log file path
func getDefaultLogPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}

	return filepath.Join(home, ".local", "share", "conductor-tui", "debug.log")
}
