package main

import (
	"fmt"
	"os"
)

// test_template.go - Simple test for template functionality
// Run with: go run . test_template

func testTemplate() {
	fmt.Println("=== Testing Template System ===")
	fmt.Println()

	// Test 1: Load templates
	fmt.Println("1. Loading templates from ~/.config/conductor-tui/templates.json")
	templates, err := loadTemplates()
	if err != nil {
		fmt.Printf("   ERROR: Failed to load templates: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("   ✓ Loaded %d templates\n\n", len(templates))

	// Test 2: Display templates
	fmt.Println("2. Available templates:")
	for i, tmpl := range templates {
		fmt.Printf("   [%d] %s (%s)\n", i+1, tmpl.Name, tmpl.Layout)
		fmt.Printf("       %s\n", tmpl.Description)
		fmt.Printf("       Working Dir: %s\n", tmpl.WorkingDir)
		fmt.Printf("       Panes: %d\n\n", len(tmpl.Panes))
	}

	// Test 3: Parse layout
	fmt.Println("3. Testing layout parsing:")
	testLayouts := []string{"2x2", "4x2", "3x3"}
	for _, layout := range testLayouts {
		cols, rows, err := parseLayout(layout)
		if err != nil {
			fmt.Printf("   ERROR: Failed to parse %s: %v\n", layout, err)
		} else {
			fmt.Printf("   ✓ %s = %d cols × %d rows = %d panes\n", layout, cols, rows, cols*rows)
		}
	}
	fmt.Println()

	// Test 4: Check if tmux is available
	fmt.Println("4. Checking tmux availability:")
	if checkTmuxRunning() {
		fmt.Println("   ✓ Tmux server is running")
	} else {
		fmt.Println("   ⚠ Tmux server is not running (start with: tmux new -s test)")
	}
	fmt.Println()

	// Test 5: List existing sessions
	fmt.Println("5. Current tmux sessions:")
	sessions, err := listSessions()
	if err != nil {
		fmt.Printf("   ERROR: %v\n", err)
	} else if len(sessions) == 0 {
		fmt.Println("   (no sessions)")
	} else {
		for _, session := range sessions {
			status := "detached"
			if session.Attached {
				status = "attached"
			}
			fmt.Printf("   • %s (%s, %d windows)\n", session.Name, status, session.Windows)
		}
	}
	fmt.Println()

	fmt.Println("=== Test Complete ===")
	fmt.Println("\nTo test session creation:")
	fmt.Println("1. Choose a template (0-based index)")
	fmt.Println("2. The app will create a session with that template")
	fmt.Println("\nTo manually test: ./conductor-tui")
	fmt.Println("Then press Enter on a template to create a session")
}
