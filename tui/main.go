package main

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"
)

// main.go - Application Entry Point
// Purpose: ONLY contains the main() function
// Rule: Never add business logic to this file. Keep it minimal.

func main() {
	// Parse command-line flags
	popupMode := false
	watcherMode := false
	cwdOverride := ""
	templateIndex := -1

	for i := 1; i < len(os.Args); i++ {
		arg := os.Args[i]
		if arg == "--popup" {
			popupMode = true
		} else if arg == "--watcher" || arg == "--sessions-only" {
			watcherMode = true
		} else if arg == "--cwd" && i+1 < len(os.Args) {
			cwdOverride = os.Args[i+1]
			i++ // Skip the next arg since we consumed it
		} else if arg == "--template" && i+1 < len(os.Args) {
			fmt.Sscanf(os.Args[i+1], "%d", &templateIndex)
			i++ // Skip the next arg since we consumed it
		}
	}

	// Check for test mode (before TTY check)
	if len(os.Args) > 1 && os.Args[1] == "test_template" {
		testTemplate()
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "test_create" {
		testCreateSession()
		return
	}

	// Handle --template flag: create session from template and exit (before TTY check)
	if templateIndex >= 0 {
		handleTemplateFlag(templateIndex, cwdOverride)
		return
	}

	// Check if we have a TTY (required for TUI mode)
	if !isTTY() {
		fmt.Println("╔═══════════════════════════════════════════════════════════════╗")
		fmt.Println("║  conductor-tui - Terminal UI Mode Requires a Real Terminal   ║")
		fmt.Println("╚═══════════════════════════════════════════════════════════════╝")
		fmt.Println()
		fmt.Println("Error: No TTY detected. conductor-tui needs to run in a real terminal.")
		fmt.Println()
		fmt.Println("📋 How to run:")
		fmt.Println("  1. Open Windows Terminal, iTerm2, or any terminal emulator")
		fmt.Println("  2. Navigate to: ~/projects/conductor-tui")
		fmt.Println("  3. Run: ./conductor-tui")
		fmt.Println()
		fmt.Println("🧪 Test without TTY:")
		fmt.Println("  ./conductor-tui test_template   - View available templates")
		fmt.Println("  ./conductor-tui test_create 0   - Create session from template 0")
		fmt.Println()
		fmt.Println("🔧 Flags:")
		fmt.Println("  --popup          - Run in popup mode (for Ctrl+b o)")
		fmt.Println("  --watcher        - Sessions-only mode (maximizes session visibility)")
		fmt.Println("  --template N     - Create session from template N and exit")
		fmt.Println()
		fmt.Println("💡 Tip: Run inside tmux for the best experience!")
		fmt.Println("   tmux new -s dev")
		fmt.Println("   cd ~/projects/conductor-tui")
		fmt.Println("   ./conductor-tui")
		fmt.Println()
		os.Exit(1)
	}

	// Load configuration
	cfg := loadConfig()

	// Create program with options based on config
	opts := []tea.ProgramOption{
		tea.WithAltScreen(),
	}

	if cfg.UI.MouseEnabled {
		opts = append(opts, tea.WithMouseCellMotion())
	}

	p := tea.NewProgram(
		initialModel(cfg, popupMode, watcherMode),
		opts...,
	)

	finalModel, err := p.Run()
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		fmt.Println()
		fmt.Println("If you see TTY errors, make sure you're running in a proper terminal.")
		os.Exit(1)
	}

	// Handle post-exit actions (like attaching to a session)
	if m, ok := finalModel.(model); ok {
		if m.attachOnExit != "" {
			// TUI has exited and released the terminal, now we can attach
			if err := attachToSession(m.attachOnExit); err != nil {
				fmt.Printf("Failed to attach to session '%s': %v\n", m.attachOnExit, err)
				os.Exit(1)
			}
			// Successfully attached - the attach command takes over the terminal
		}
	}
}

// handleTemplateFlag creates a session from a template and exits
func handleTemplateFlag(templateIndex int, cwdOverride string) {
	// Load templates
	templates, err := loadTemplates()
	if err != nil {
		fmt.Printf("Error: Failed to load templates: %v\n", err)
		os.Exit(1)
	}

	// Validate template index
	if templateIndex < 0 || templateIndex >= len(templates) {
		fmt.Printf("Error: Invalid template index %d (valid range: 0-%d)\n", templateIndex, len(templates)-1)
		fmt.Println("\nAvailable templates:")
		for i, t := range templates {
			fmt.Printf("  %d: %s\n", i, t.Name)
		}
		os.Exit(1)
	}

	template := templates[templateIndex]

	// Show what we're doing
	fmt.Printf("Creating session from template: %s\n", template.Name)
	if cwdOverride != "" {
		fmt.Printf("Working directory override: %s\n", cwdOverride)
	} else {
		fmt.Printf("Working directory: %s\n", template.WorkingDir)
	}

	// Create session from template
	sessionName, err := createSessionFromTemplateWithOverride(template, cwdOverride)
	if err != nil {
		fmt.Printf("Error: Failed to create session: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("\n✓ Session '%s' created successfully!\n", sessionName)
	fmt.Printf("\nTo attach to the session:\n")
	fmt.Printf("  tmux attach -t %s\n", sessionName)
}

// isTTY checks if we have a TTY available
func isTTY() bool {
	if _, err := os.Stat("/dev/tty"); os.IsNotExist(err) {
		return false
	}
	// Try to open /dev/tty
	tty, err := os.OpenFile("/dev/tty", os.O_RDWR, 0)
	if err != nil {
		return false
	}
	defer tty.Close()
	return true
}
