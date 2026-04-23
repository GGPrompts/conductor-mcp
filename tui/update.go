package main

import (
	"fmt"
	"time"

	tea "github.com/charmbracelet/bubbletea"
)

// update.go - Main Update Dispatcher
// Purpose: Message dispatching and non-input event handling
// When to extend: Add new message types or top-level event handlers here

// Init is called when the program starts
func (m model) Init() tea.Cmd {
	// Start auto-refresh ticker (2 seconds)
	return tea.Batch(
		tickCmd(),
	)
}

// Update handles all messages and updates the model
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {

	// Window resize
	case tea.WindowSizeMsg:
		m.setSize(msg.Width, msg.Height)
		return m, nil

	// Keyboard input
	case tea.KeyMsg:
		return m.handleKeyPress(msg)

	// Mouse input
	case tea.MouseMsg:
		return m.handleMouseEvent(msg)

	// Custom messages
	case errMsg:
		m.err = msg.err
		m.statusMsg = "Error: " + msg.err.Error()
		return m, nil

	case statusMsg:
		m.statusMsg = msg.message
		return m, nil

	case sessionCreatedMsg:
		if msg.err != nil {
			m.statusMsg = "Failed to create session: " + msg.err.Error()
		} else {
			m.statusMsg = "✓ Session created: " + msg.sessionName + " | Press Ctrl+R to refresh"
		}
		// Refresh session list
		return m, refreshSessionsCmd()

	case sessionCreatedAndAttachMsg:
		if msg.err != nil {
			m.statusMsg = "Failed to create session: " + msg.err.Error()
			return m, nil
		}

		// Session created successfully, now attach to it
		m.statusMsg = "Session '" + msg.sessionName + "' created! Attaching..."
		if m.popupMode {
			// In popup mode, switch client directly and quit
			if err := switchClient(msg.sessionName); err != nil {
				m.statusMsg = "Failed to switch to session: " + err.Error()
				return m, nil
			}
			return m, tea.Quit
		} else {
			// In normal mode, set session to attach on exit
			m.attachOnExit = msg.sessionName
			return m, tea.Quit
		}

	case sessionsLoadedMsg:
		// Preserve selection by tree item details (session name, window index, pane index, type)
		var selectedSessionName string
		var selectedWindowIndex int = -1
		var selectedPaneIndex int = -1
		var selectedType string

		if m.selectedSession >= 0 && m.selectedSession < len(m.sessionTreeItems) {
			item := m.sessionTreeItems[m.selectedSession]
			if item.Session != nil {
				selectedSessionName = item.Session.Name
				selectedType = item.Type
				selectedWindowIndex = item.WindowIndex
				selectedPaneIndex = item.PaneIndex
			}
		}

		// Update sessions list
		m.sessions = msg.sessions

		// Rebuild tree with updated sessions
		m.updateSessionTreeItems()

		// Restore selection to the same tree item
		if selectedSessionName != "" && len(m.sessionTreeItems) > 0 {
			found := false
			for i, item := range m.sessionTreeItems {
				if item.Session != nil && item.Session.Name == selectedSessionName {
					// Match by type and indices
					if item.Type == selectedType {
						if selectedType == "session" {
							// Session match - good enough
							m.selectedSession = i
							found = true
							break
						} else if selectedType == "window" && item.WindowIndex == selectedWindowIndex {
							// Window match
							m.selectedSession = i
							found = true
							break
						} else if selectedType == "pane" && item.WindowIndex == selectedWindowIndex && item.PaneIndex == selectedPaneIndex {
							// Exact pane match
							m.selectedSession = i
							found = true
							break
						}
					}
				}
			}

			// If exact item not found, try to find just the session
			if !found {
				for i, item := range m.sessionTreeItems {
					if item.Session != nil && item.Session.Name == selectedSessionName && item.Type == "session" {
						m.selectedSession = i
						found = true
						break
					}
				}
			}

			// If session no longer exists, select first item
			if !found {
				m.selectedSession = 0
			}
		} else if len(m.sessionTreeItems) > 0 {
			// No previous selection, select first item
			m.selectedSession = 0
		}

		m.updateCommandContent()
		m.updateSessionsContent()
		m.updateTemplatesContent()
		m.updatePreviewContent() // Update preview when sessions are loaded
		return m, nil

	case sessionKilledMsg:
		if msg.err != nil {
			m.statusMsg = "Failed to kill session: " + msg.err.Error()
		} else {
			m.statusMsg = "✓ Killed session: " + msg.sessionName
		}
		// Refresh session list
		return m, refreshSessionsCmd()

	case sessionDetachedMsg:
		if msg.err != nil {
			m.statusMsg = "Failed to detach from session: " + msg.err.Error()
		} else {
			m.statusMsg = "✓ Detached from session: " + msg.sessionName
		}
		// Refresh session list
		return m, refreshSessionsCmd()

	case sessionRenamedMsg:
		if msg.err != nil {
			m.statusMsg = "Failed to rename session: " + msg.err.Error()
		} else {
			m.statusMsg = "✓ Renamed session: " + msg.oldName + " → " + msg.newName
		}
		// Refresh session list
		return m, refreshSessionsCmd()

	case commandSentMsg:
		if msg.err != nil {
			m.statusMsg = "Failed to send command: " + msg.err.Error()
		} else {
			m.statusMsg = "✓ Command sent to " + msg.sessionName
		}
		return m, nil

	case templatesReloadedMsg:
		if msg.err != nil {
			m.statusMsg = "Failed to reload templates: " + msg.err.Error()
		} else {
			m.templates = msg.templates
			m.statusMsg = "✓ Templates reloaded"
			m.updateTemplatesContent()
		}
		return m, nil

	case commandEditedMsg:
		if msg.err != nil {
			m.statusMsg = "Editor error: " + msg.err.Error()
		} else {
			m.commandInput = msg.content
			m.commandCursor = len(msg.content)
			m.updateCommandContent()
			if msg.content != "" {
				m.statusMsg = fmt.Sprintf("✓ Loaded %d characters from editor", len(msg.content))
			} else {
				m.statusMsg = "Editor closed (empty content)"
			}
		}
		return m, nil

	case templateSavedMsg:
		if msg.err != nil {
			m.statusMsg = "Failed to save template: " + msg.err.Error()
		} else {
			m.statusMsg = "✓ Template saved: " + msg.template.Name
			// Reload templates to show the new one
			templates, err := loadTemplates()
			if err == nil {
				m.templates = templates
				m.updateTemplatesContent()
			}
		}
		return m, nil

	case templateDeletedMsg:
		if msg.err != nil {
			m.statusMsg = "Failed to delete template: " + msg.err.Error()
		} else {
			m.statusMsg = "✓ Template deleted"
			// Reload templates to update the list
			templates, err := loadTemplates()
			if err == nil {
				m.templates = templates
				// Adjust selected index if needed
				if m.selectedTemplate >= len(m.templates) && len(m.templates) > 0 {
					m.selectedTemplate = len(m.templates) - 1
				}
				m.updateTemplatesContent()
			}
		}
		return m, nil

	case sessionExtractedMsg:
		if msg.err != nil {
			m.statusMsg = "Failed to extract session: " + msg.err.Error()
			return m, nil
		}

		// Convert interface{} back to ExtractedSessionInfo
		info, ok := msg.info.(*ExtractedSessionInfo)
		if !ok {
			m.statusMsg = "Failed to extract session: invalid info type"
			return m, nil
		}

		// Convert extracted panes to PaneTemplate format
		panes := make([]PaneTemplate, len(info.Panes))
		workingDirCounts := make(map[string]int)

		for i, pane := range info.Panes {
			panes[i] = PaneTemplate{
				Command:    pane.Command,
				Title:      pane.Title,
				WorkingDir: pane.WorkingDir,
			}
			// Count working directory occurrences
			workingDirCounts[pane.WorkingDir]++
		}

		// Find the most common working directory
		commonWorkDir := "~"
		maxCount := 0
		for dir, count := range workingDirCounts {
			if count > maxCount {
				maxCount = count
				commonWorkDir = dir
			}
		}

		// Detect layout
		layout := detectGridLayout(info.Panes)

		// Enter session save mode
		m.sessionSaveMode = true
		m.sessionBuilder = SessionSaveBuilder{
			sessionName:   msg.sessionName,
			name:          msg.sessionName, // Default name
			layout:        layout,
			panes:         panes,
			fieldName:     "name",
			extractedInfo: info,
			commonWorkDir: commonWorkDir,
		}
		m.inputBuffer = msg.sessionName // Pre-fill with session name
		m.statusMsg = "Session extracted - enter template name"
		return m, nil

	case voiceTestResultMsg:
		// Surface the async voice preview outcome in the status bar. Previous
		// code swallowed this with `go func(){ _ = testVoice(...) }()`.
		if msg.err != nil {
			m.statusMsg = "Voice test failed (" + msg.voice + "): " + msg.err.Error()
		}
		// Success leaves the existing "Preview:"/"Saved voice:"/"Testing:"
		// status intact — no need to overwrite it.
		return m, nil

	case tickMsg:
		// Auto-refresh sessions every 2 seconds
		// Preserve the currently selected item
		return m, tea.Batch(
			refreshSessionsCmd(),
			tickCmd(),
		)

	case footerTickMsg:
		// Animate footer scrolling if active
		if m.footerScrolling {
			m.footerOffset++
			return m, footerTick() // Continue scrolling
		}
		// If scrolling was stopped, don't schedule next tick

	// Add handlers for your custom messages here
	// Example:
	// case itemSelectedMsg:
	//     return m.handleItemSelected(msg)
	//
	// case dataLoadedMsg:
	//     return m.handleDataLoaded(msg)
	}

	return m, nil
}

// Helper functions for message handling

// sendStatus creates a status message command
func sendStatus(message string) tea.Cmd {
	return func() tea.Msg {
		return statusMsg{message: message}
	}
}

// sendError creates an error message command
func sendError(err error) tea.Cmd {
	return func() tea.Msg {
		return errMsg{err: err}
	}
}

// isSpecialKey checks if a key is a special key (not printable)
func isSpecialKey(key tea.KeyMsg) bool {
	return key.Type != tea.KeyRunes
}

// refreshSessionsCmd creates a command to reload tmux sessions
func refreshSessionsCmd() tea.Cmd {
	return func() tea.Msg {
		sessions, err := listSessions()
		if err != nil {
			// Return empty list on error
			sessions = []TmuxSession{}
		}
		return sessionsLoadedMsg{sessions: sessions}
	}
}

// tickCmd creates a command that ticks after 2 seconds
func tickCmd() tea.Cmd {
	return tea.Tick(2*time.Second, func(t time.Time) tea.Msg {
		return tickMsg{}
	})
}

// footerTick sends periodic messages to animate footer scrolling
func footerTick() tea.Cmd {
	return tea.Tick(200*time.Millisecond, func(t time.Time) tea.Msg {
		return footerTickMsg{}
	})
}

// testVoiceCmd runs testVoice in a goroutine-safe tea.Cmd and returns a
// voiceTestResultMsg back through the Update loop. Replaces the earlier
// fire-and-forget `go func(){ _ = testVoice(...) }()` pattern so TTS
// failures surface to the user in the status bar instead of disappearing.
func testVoiceCmd(voice, rate, text string) tea.Cmd {
	return func() tea.Msg {
		return voiceTestResultMsg{voice: voice, err: testVoice(voice, rate, text)}
	}
}
