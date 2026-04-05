package main

import (
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// config.go - Configuration Management
// Purpose: Load and manage application configuration
// When to extend: Add new configuration options or loaders

// loadConfig loads configuration from file or returns defaults
func loadConfig() Config {
	// Try to load from config file
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

// loadConfigFile loads configuration from ~/.config/conductor-tui/config.yaml
func loadConfigFile() (Config, error) {
	configPath := getConfigPath()

	data, err := os.ReadFile(configPath)
	if err != nil {
		return Config{}, err
	}

	var cfg Config
	err = yaml.Unmarshal(data, &cfg)
	if err != nil {
		return Config{}, err
	}

	// Validate and apply defaults for missing fields
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

// saveConfig saves the current configuration to file
func saveConfig(cfg Config) error {
	configPath := getConfigPath()

	// Create config directory if it doesn't exist
	configDir := filepath.Dir(configPath)
	if err := os.MkdirAll(configDir, 0755); err != nil {
		return err
	}

	// Marshal config to YAML
	data, err := yaml.Marshal(cfg)
	if err != nil {
		return err
	}

	// Write to file
	return os.WriteFile(configPath, data, 0644)
}

// getConfigPath returns the path to the config file
func getConfigPath() string {
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

// createExampleConfig creates an example config file
func createExampleConfig() error {
	examplePath := filepath.Join(filepath.Dir(getConfigPath()), "config.yaml.example")

	example := `# Tmuxplexer Configuration File

# Theme: dark, light, solarized, dracula, nord, custom
theme: "dark"

# Custom theme (if theme: custom)
# custom_theme:
#   primary: "#61AFEF"
#   secondary: "#C678DD"
#   background: "#282C34"
#   foreground: "#ABB2BF"
#   accent: "#98C379"
#   error: "#E06C75"

# Keybindings: default, vim, emacs, custom
keybindings: "default"

# Custom keybindings (if keybindings: custom)
# custom_keybindings:
#   quit: "q"
#   help: "?"
#   search: "/"

# Layout
layout:
  type: "single"  # single, dual_pane, multi_panel, tabbed
  split_ratio: 0.5
  show_divider: true

# UI Elements
ui:
  show_title: true
  show_status: true
  show_line_numbers: false
  mouse_enabled: true
  show_icons: true
  icon_set: "nerd_font"  # nerd_font, ascii, unicode

# Performance
performance:
  lazy_loading: true
  cache_size: 100
  async_operations: true

# Logging
logging:
  enabled: false
  level: "info"  # debug, info, warn, error
  file: "~/.local/share/conductor-tui/debug.log"
`

	// Create directory if it doesn't exist
	dir := filepath.Dir(examplePath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	return os.WriteFile(examplePath, []byte(example), 0644)
}
