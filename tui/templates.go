package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
)

// templates.go - Template Management
// Purpose: Load, save, and manage workspace templates

// getTemplatesPath returns the path to the templates.json file
func getTemplatesPath() (string, error) {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}

	configDir := filepath.Join(homeDir, ".config", "conductor-tui")
	// Ensure config directory exists
	if err := os.MkdirAll(configDir, 0755); err != nil {
		return "", err
	}

	return filepath.Join(configDir, "templates.json"), nil
}

// loadTemplates loads templates from ~/.config/conductor-tui/templates.json
// If the file doesn't exist, it creates it with default templates
func loadTemplates() ([]SessionTemplate, error) {
	templatesPath, err := getTemplatesPath()
	if err != nil {
		return nil, err
	}

	// Check if file exists
	if _, err := os.Stat(templatesPath); os.IsNotExist(err) {
		// Create default templates
		defaultTemplates := getDefaultTemplates()
		if err := saveTemplates(defaultTemplates); err != nil {
			return nil, err
		}
		return defaultTemplates, nil
	}

	// Read existing file
	data, err := os.ReadFile(templatesPath)
	if err != nil {
		return nil, err
	}

	var templates []SessionTemplate
	if err := json.Unmarshal(data, &templates); err != nil {
		return nil, err
	}

	// Migrate templates to add category field if missing
	templates, modified := migrateTemplates(templates)
	if modified {
		// Save migrated templates
		if err := saveTemplates(templates); err != nil {
			return nil, err
		}
	}

	return templates, nil
}

// migrateTemplates adds default category to templates that don't have one
func migrateTemplates(templates []SessionTemplate) ([]SessionTemplate, bool) {
	modified := false
	for i := range templates {
		if templates[i].Category == "" {
			templates[i].Category = "Uncategorized"
			modified = true
		}
	}
	return templates, modified
}

// saveTemplates saves templates to ~/.config/conductor-tui/templates.json
func saveTemplates(templates []SessionTemplate) error {
	templatesPath, err := getTemplatesPath()
	if err != nil {
		return err
	}

	data, err := json.MarshalIndent(templates, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(templatesPath, data, 0644)
}

// getDefaultTemplates returns a set of built-in templates
func getDefaultTemplates() []SessionTemplate {
	return []SessionTemplate{
		{
			Name:        "Simple Dev (2x2)",
			Description: "Basic development workspace with editor, terminal, git, and monitoring",
			Category:    "Projects",
			WorkingDir:  "~",
			Layout:      "2x2",
			Panes: []PaneTemplate{
				{Command: "nvim", Title: "Editor"},
				{Command: "bash", Title: "Terminal"},
				{Command: "lazygit", Title: "Git"},
				{Command: "btop", Title: "Monitor"},
			},
		},
		{
			Name:        "Frontend Dev (2x2)",
			Description: "Frontend workspace with Claude, editor, dev server, and git",
			Category:    "Projects",
			WorkingDir:  "~",
			Layout:      "2x2",
			Panes: []PaneTemplate{
				{Command: "claude-code .", Title: "Claude AI"},
				{Command: "nvim", Title: "Editor"},
				{Command: "npm run dev", Title: "Dev Server"},
				{Command: "lazygit", Title: "Git"},
			},
		},
		{
			Name:        "TFE Development (4x2)",
			Description: "Full TFE development environment with 8 panes",
			Category:    "Projects",
			WorkingDir:  "~/projects/TFE",
			Layout:      "4x2",
			Panes: []PaneTemplate{
				{Command: "claude-code .", Title: "Claude AI"},
				{Command: "nvim", Title: "Editor"},
				{Command: "npm run dev", Title: "Dev Server"},
				{Command: "lazygit", Title: "Git"},
				{Command: "./tfe .", Title: "TFE Browser"},
				{Command: "npm test -- --watch", Title: "Tests"},
				{Command: "btop", Title: "Monitor"},
				{Command: "docker compose logs -f || bash", Title: "Logs"},
			},
		},
		{
			Name:        "Monitoring Wall (4x2)",
			Description: "System monitoring dashboard with multiple tools",
			Category:    "Tools",
			WorkingDir:  "~",
			Layout:      "4x2",
			Panes: []PaneTemplate{
				{Command: "btop", Title: "System Monitor"},
				{Command: "watch -n 1 df -h", Title: "Disk Usage"},
				{Command: "watch -n 1 free -h", Title: "Memory"},
				{Command: "watch -n 1 'docker ps'", Title: "Docker"},
				{Command: "journalctl -f", Title: "System Logs"},
				{Command: "watch -n 1 'netstat -tuln'", Title: "Network"},
				{Command: "watch -n 1 'systemctl --failed'", Title: "Services"},
				{Command: "bash", Title: "Terminal"},
			},
		},
	}
}

// buildListItems creates a combined list of templates and sessions for the left panel
func buildListItems(templates []SessionTemplate, sessions []TmuxSession) []TemplateListItem {
	var items []TemplateListItem

	// Add templates section
	for i := range templates {
		items = append(items, TemplateListItem{
			Type:        "template",
			Name:        templates[i].Name,
			Description: templates[i].Description,
			Template:    &templates[i],
		})
	}

	// Add sessions section
	for i := range sessions {
		status := "detached"
		if sessions[i].Attached {
			status = "attached"
		}
		items = append(items, TemplateListItem{
			Type:        "session",
			Name:        sessions[i].Name,
			Description: status + " • " + sessions[i].LastActive,
			Session:     &sessions[i],
		})
	}

	return items
}

// getUserEditor returns the user's preferred editor command and args
// Priority: $EDITOR env var > micro > nano > vim > vi
// Returns: (command, args, found)
func getUserEditor() (string, []string, bool) {
	// Check EDITOR environment variable
	if editor := os.Getenv("EDITOR"); editor != "" {
		// Parse editor string (may contain flags like "code --wait")
		// Split on spaces but be careful with quoted strings
		parts := splitEditorCommand(editor)
		if len(parts) > 0 {
			// Check if the command is executable
			if _, err := exec.LookPath(parts[0]); err == nil {
				return parts[0], parts[1:], true
			}
		}
	}

	// Try common editors in order of preference
	editors := []string{"micro", "nano", "vim", "vi"}
	for _, editor := range editors {
		if _, err := exec.LookPath(editor); err == nil {
			return editor, []string{}, true
		}
	}

	// Try VS Code with --wait flag (blocks until editor closes)
	// Only as fallback if common terminal editors aren't found
	if _, err := exec.LookPath("code"); err == nil {
		return "code", []string{"--wait"}, true
	}

	// Final fallback to vi (should always exist on Unix systems)
	return "vi", []string{}, false
}

// splitEditorCommand splits an editor command string into command and args
// Handles simple cases like "code --wait" or "vim"
func splitEditorCommand(cmd string) []string {
	// Simple split on spaces - good enough for most cases
	// Could be enhanced to handle quoted args if needed
	var parts []string
	current := ""
	for _, char := range cmd {
		if char == ' ' {
			if current != "" {
				parts = append(parts, current)
				current = ""
			}
		} else {
			current += string(char)
		}
	}
	if current != "" {
		parts = append(parts, current)
	}
	return parts
}

// openTemplatesInEditor opens the templates.json file in the user's editor
// Returns error if the editor could not be started
func openTemplatesInEditor() error {
	templatesPath, err := getTemplatesPath()
	if err != nil {
		return err
	}

	editor, args, _ := getUserEditor()

	// Build command with args + file path
	allArgs := append(args, templatesPath)
	cmd := exec.Command(editor, allArgs...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	return cmd.Run()
}

// addTemplate adds a new template to the templates file
func addTemplate(template SessionTemplate) error {
	templates, err := loadTemplates()
	if err != nil {
		return err
	}

	templates = append(templates, template)
	return saveTemplates(templates)
}

// deleteTemplate deletes a template at the given index
func deleteTemplate(index int) error {
	templates, err := loadTemplates()
	if err != nil {
		return err
	}

	if index < 0 || index >= len(templates) {
		return nil // Invalid index, do nothing
	}

	// Remove template at index
	templates = append(templates[:index], templates[index+1:]...)
	return saveTemplates(templates)
}
