package main

import (
	"fmt"
	"os"
	"time"
)

// test_create_session.go - Test creating a session from a template
// Run with: go run . test_create <template_index>

func testCreateSession() {
	if len(os.Args) < 3 {
		fmt.Println("Usage: ./conductor-tui test_create <template_index>")
		fmt.Println("\nAvailable templates:")

		templates, err := loadTemplates()
		if err != nil {
			fmt.Printf("ERROR: Failed to load templates: %v\n", err)
			os.Exit(1)
		}

		for i, tmpl := range templates {
			fmt.Printf("  [%d] %s (%s)\n", i, tmpl.Name, tmpl.Layout)
		}
		os.Exit(1)
	}

	// Parse template index
	var templateIdx int
	_, err := fmt.Sscanf(os.Args[2], "%d", &templateIdx)
	if err != nil {
		fmt.Printf("ERROR: Invalid template index: %s\n", os.Args[2])
		os.Exit(1)
	}

	// Load templates
	templates, err := loadTemplates()
	if err != nil {
		fmt.Printf("ERROR: Failed to load templates: %v\n", err)
		os.Exit(1)
	}

	if templateIdx < 0 || templateIdx >= len(templates) {
		fmt.Printf("ERROR: Template index %d out of range (0-%d)\n", templateIdx, len(templates)-1)
		os.Exit(1)
	}

	template := templates[templateIdx]
	fmt.Printf("Creating session from template: %s\n", template.Name)
	fmt.Printf("Layout: %s (%d panes)\n", template.Layout, len(template.Panes))
	fmt.Printf("Working Dir: %s\n\n", template.WorkingDir)

	// Ensure tmux is running
	if !checkTmuxRunning() {
		fmt.Println("Starting tmux server...")
		if err := startTmuxServer(); err != nil {
			fmt.Printf("ERROR: Failed to start tmux: %v\n", err)
			os.Exit(1)
		}
		time.Sleep(500 * time.Millisecond)
	}

	// Create the session
	fmt.Println("Creating session...")
	sessionName, err := createSessionFromTemplate(template)
	if err != nil {
		fmt.Printf("ERROR: Failed to create session: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("✓ Session '%s' created successfully!\n", sessionName)

	// Wait a moment for commands to execute
	time.Sleep(1 * time.Second)

	// List sessions to verify
	fmt.Println("\nCurrent sessions:")
	sessions, err := listSessions()
	if err != nil {
		fmt.Printf("ERROR: Failed to list sessions: %v\n", err)
		os.Exit(1)
	}

	for _, session := range sessions {
		status := "detached"
		if session.Attached {
			status = "attached"
		}
		fmt.Printf("  • %s (%s, %d windows)\n", session.Name, status, session.Windows)
	}

	fmt.Println("\nTo attach to the session:")
	fmt.Printf("  tmux attach -t %s\n", sessionName)
}
