package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"

	"github.com/atotto/clipboard"
	"github.com/charmbracelet/bubbles/key"
	tea "github.com/charmbracelet/bubbletea"
)

// update_keyboard.go - Keyboard Event Handling
// Purpose: All keyboard input processing
// When to extend: Add new keyboard shortcuts or key bindings here

// handleKeyPress handles keyboard input
func (m model) handleKeyPress(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	// Shift+Tab ALWAYS has priority (allows escaping from any mode)
	// BUT: Tab, 1, 2, 3 only switch panels when NOT in active command input
	switch msg.String() {
	case "shift+tab":
		return m.handleMainKeys(msg)
	case "tab", "1", "2", "3":
		// Allow typing these keys in command mode
		if m.focusState != FocusCommand {
			return m.handleMainKeys(msg)
		}
		// Otherwise fall through to command input handling
	}

	// Handle session save mode
	if m.sessionSaveMode {
		return m.handleSessionSaveInput(msg)
	}

	// Handle template creation mode
	if m.templateCreationMode {
		return m.handleTemplateCreationInput(msg)
	}

	// Handle input mode (e.g., renaming sessions)
	if m.inputMode == "rename" {
		switch msg.Type {
		case tea.KeyEsc:
			// Cancel rename
			m.inputMode = ""
			m.inputBuffer = ""
			m.inputPrompt = ""
			m.renameTarget = ""
			m.statusMsg = "Rename cancelled"
			return m, nil

		case tea.KeyEnter:
			// Confirm rename
			newName := m.inputBuffer
			oldName := m.renameTarget

			// Clear input mode
			m.inputMode = ""
			m.inputBuffer = ""
			m.inputPrompt = ""
			m.renameTarget = ""

			// Validate new name
			if newName == "" || newName == oldName {
				m.statusMsg = "Rename cancelled (no change)"
				return m, nil
			}

			// Execute rename
			m.statusMsg = "Renaming session '" + oldName + "' to '" + newName + "'..."
			return m, m.renameSessionCmd(oldName, newName)

		case tea.KeyBackspace:
			// Remove last character
			if len(m.inputBuffer) > 0 {
				m.inputBuffer = m.inputBuffer[:len(m.inputBuffer)-1]
			}
			return m, nil

		case tea.KeySpace:
			// Replace spaces with hyphens for session names (tmux convention)
			m.inputBuffer += "-"
			return m, nil

		case tea.KeyRunes:
			// Add typed characters
			m.inputBuffer += string(msg.Runes)
			return m, nil
		}

		// Other keys ignored in input mode
		return m, nil
	}

	// Handle template delete confirmation
	if m.inputMode == "template_delete_confirm" {
		switch msg.String() {
		case "y", "Y":
			// Confirm delete
			m.inputMode = ""
			m.inputPrompt = ""
			m.statusMsg = "Deleting template..."
			return m, m.deleteTemplateCmd(m.selectedTemplate)

		case "n", "N", "esc":
			// Cancel delete
			m.inputMode = ""
			m.inputPrompt = ""
			m.statusMsg = "Template deletion cancelled"
			return m, nil
		}
		return m, nil
	}

	// Handle kill session confirmation
	if m.inputMode == "kill_confirm" {
		switch msg.String() {
		case "y", "Y":
			// Confirm kill
			m.inputMode = ""
			m.inputPrompt = ""
			// Get the selected session
			if len(m.sessionTreeItems) > 0 && m.selectedSession < len(m.sessionTreeItems) {
				item := m.sessionTreeItems[m.selectedSession]
				if item.Type == "session" && item.Session != nil {
					m.statusMsg = "Killing session: " + item.Session.Name + "..."
					return m, m.killSessionCmd(item.Session.Name)
				}
			}
			m.statusMsg = "No session selected"
			return m, nil

		case "n", "N", "esc":
			// Cancel kill
			m.inputMode = ""
			m.inputPrompt = ""
			m.statusMsg = "Kill cancelled"
			return m, nil
		}
		return m, nil
	}

	// Handle command input on Chat tab
	if m.focusState == FocusCommand {
		switch msg.Type {
		case tea.KeyEsc:
			// ESC on Command panel clears input and unfocuses
			m.commandInput = ""
			m.commandCursor = 0
			m.historyIndex = -1
			m.focusState = FocusSessions
			m.statusMsg = "Command cleared"
			m.updateCommandContent()
			return m, nil

		case tea.KeyEnter:
			// Execute command
			if m.commandInput != "" {
				return m.executeCommand()
			}
			return m, nil

		case tea.KeyUp:
			// Navigate history backwards
			if len(m.commandHistory) > 0 {
				if m.historyIndex == -1 {
					m.historyIndex = len(m.commandHistory) - 1
				} else if m.historyIndex > 0 {
					m.historyIndex--
				}
				if m.historyIndex >= 0 && m.historyIndex < len(m.commandHistory) {
					m.commandInput = m.commandHistory[m.historyIndex]
					m.commandCursor = len(m.commandInput)
				}
				m.updateCommandContent()
			}
			return m, nil

		case tea.KeyDown:
			// Navigate history forwards
			if m.historyIndex != -1 {
				m.historyIndex++
				if m.historyIndex >= len(m.commandHistory) {
					m.historyIndex = -1
					m.commandInput = ""
					m.commandCursor = 0
				} else {
					m.commandInput = m.commandHistory[m.historyIndex]
					m.commandCursor = len(m.commandInput)
				}
				m.updateCommandContent()
			}
			return m, nil

		case tea.KeyLeft:
			// Move cursor left
			if m.commandCursor > 0 {
				m.commandCursor--
				m.updateCommandContent()
			}
			return m, nil

		case tea.KeyRight:
			// Move cursor right
			if m.commandCursor < len(m.commandInput) {
				m.commandCursor++
				m.updateCommandContent()
			}
			return m, nil

		case tea.KeyBackspace:
			// Delete character before cursor
			if m.commandCursor > 0 && len(m.commandInput) > 0 {
				runes := []rune(m.commandInput)
				m.commandInput = string(runes[:m.commandCursor-1]) + string(runes[m.commandCursor:])
				m.commandCursor--
				m.updateCommandContent()
			}
			return m, nil

		case tea.KeyDelete:
			// Delete character at cursor
			if m.commandCursor < len(m.commandInput) {
				runes := []rune(m.commandInput)
				m.commandInput = string(runes[:m.commandCursor]) + string(runes[m.commandCursor+1:])
				m.updateCommandContent()
			}
			return m, nil

		case tea.KeySpace:
			// Insert space at cursor
			runes := []rune(m.commandInput)
			m.commandInput = string(runes[:m.commandCursor]) + " " + string(runes[m.commandCursor:])
			m.commandCursor++
			m.updateCommandContent()
			return m, nil

		case tea.KeyTab:
			// Insert tab at cursor (useful for shell commands)
			runes := []rune(m.commandInput)
			m.commandInput = string(runes[:m.commandCursor]) + "\t" + string(runes[m.commandCursor:])
			m.commandCursor++
			m.updateCommandContent()
			return m, nil

		case tea.KeyCtrlV:
			// Paste clipboard content at cursor
			clipboardText, err := clipboard.ReadAll()
			if err != nil {
				m.statusMsg = "Failed to read clipboard"
				return m, nil
			}

			// Convert multi-line clipboard content to single line
			// Replace newlines with spaces for better command formatting
			clipboardText = strings.ReplaceAll(clipboardText, "\n", " ")
			clipboardText = strings.ReplaceAll(clipboardText, "\r", "")

			// Insert clipboard text at cursor position
			runes := []rune(m.commandInput)
			m.commandInput = string(runes[:m.commandCursor]) + clipboardText + string(runes[m.commandCursor:])

			// Update cursor position to end of pasted text
			m.commandCursor += len([]rune(clipboardText))

			// Update display
			m.updateCommandContent()

			// Show confirmation message with paste length
			pasteLen := len([]rune(clipboardText))
			if pasteLen > 1000 {
				m.statusMsg = fmt.Sprintf("Pasted %d characters (large paste)", pasteLen)
			} else {
				m.statusMsg = fmt.Sprintf("Pasted %d characters", pasteLen)
			}
			return m, nil

		case tea.KeyCtrlG:
			// Open external editor to edit command (like Claude Code's Ctrl+G)
			m.statusMsg = "Opening editor..."
			return m, m.editCommandCmd()

		case tea.KeyRunes:
			// Insert character at cursor (all other characters)
			runes := []rune(m.commandInput)
			m.commandInput = string(runes[:m.commandCursor]) + string(msg.Runes) + string(runes[m.commandCursor:])
			m.commandCursor += len(msg.Runes)
			m.updateCommandContent()
			return m, nil
		}

		// All other keys are ignored in command mode (not passed through)
		// This prevents keys like 'a', '1', '2' from triggering other actions
		return m, nil
	}

	// Global keybindings (work in all modes)
	switch {
	case key.Matches(msg, keys.Quit):
		return m, tea.Quit

	case msg.String() == "X":
		// X in popup mode: detach and launch fullscreen conductor-tui
		if m.popupMode {
			m.statusMsg = "Detaching and launching fullscreen..."
			err := detachAndLaunchFullscreen()
			if err != nil {
				m.statusMsg = "Failed to launch fullscreen: " + err.Error()
				return m, nil
			}
			// Quit the popup (fullscreen conductor-tui will take over)
			return m, tea.Quit
		}
		return m, nil

	case msg.Type == tea.KeyEsc:
		// ESC closes popup in popup mode, otherwise does nothing
		if m.popupMode {
			return m, tea.Quit
		}
		return m, nil

	case key.Matches(msg, keys.Help):
		return m.showHelp()

	case key.Matches(msg, keys.Refresh):
		return m.refresh()

	case msg.String() == "ctrl+r":
		m.statusMsg = "Refreshing sessions..."
		return m, refreshSessionsCmd()
	}

	// Mode-specific keybindings
	switch m.focusedComponent {
	case "main":
		return m.handleMainKeys(msg)

	// Add handlers for other components/modes
	// case "dialog":
	//     return m.handleDialogKeys(msg)
	//
	// case "menu":
	//     return m.handleMenuKeys(msg)
	}

	return m, nil
}

// handleMainKeys handles keys in main view
func (m model) handleMainKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {

	// Panel focus (1-3, top to bottom)
	case "1":
		// Focus sessions/templates panel (top)
		// If already focused, toggle between Sessions and Templates tabs
		if m.focusState == FocusSessions {
			// Already focused - toggle tab
			if m.sessionsTab == "sessions" {
				m.sessionsTab = "templates"
				m.statusMsg = "Tab: Templates"
				m.sessionsScrollOffset = 0 // Reset scroll when switching tabs
				m.updateTemplatesContent()
				m.updatePreviewContent() // Update preview to show template details
			} else {
				m.sessionsTab = "sessions"
				m.statusMsg = "Tab: Sessions"
				m.sessionsScrollOffset = 0 // Reset scroll when switching tabs
				m.updateSessionsContent()
				m.updatePreviewContent() // Update preview to show session preview
			}
		} else {
			// Not focused - focus the panel
			m.focusState = FocusSessions
			if m.sessionsTab == "templates" {
				m.statusMsg = "Focus: Templates"
			} else {
				m.statusMsg = "Focus: Sessions"
			}
		}
		return m, nil
	case "2":
		// Focus preview panel (middle) - only if not maximized
		if m.sessionsMaximized {
			m.statusMsg = "Preview hidden (press 'z' to restore)"
			return m, nil
		}
		m.focusState = FocusPreview
		m.statusMsg = "Focus: Preview"
		return m, nil
	case "3":
		// Focus command panel (bottom)
		m.focusState = FocusCommand
		m.statusMsg = "Focus: Command"
		return m, nil

	case "z":
		// Toggle maximize mode for sessions panel (hides preview)
		m.sessionsMaximized = !m.sessionsMaximized
		if m.sessionsMaximized {
			m.statusMsg = "Sessions maximized (press 'z' to restore)"
			// If preview was focused, switch to sessions
			if m.focusState == FocusPreview {
				m.focusState = FocusSessions
			}
		} else {
			m.statusMsg = "Sessions restored"
		}
		return m, nil

	// Focus cycling (Tab / Shift+Tab)
	case "tab":
		// Cycle forward: Sessions → Preview → Command → Sessions...
		// When maximized, skip Preview: Sessions → Command → Sessions...
		m.focusState = (m.focusState + 1) % 3
		if m.sessionsMaximized && m.focusState == FocusPreview {
			m.focusState = FocusCommand // Skip preview when maximized
		}
		switch m.focusState {
		case FocusSessions:
			m.statusMsg = "Focus: Sessions"
		case FocusPreview:
			m.statusMsg = "Focus: Preview"
		case FocusCommand:
			m.statusMsg = "Focus: Command"
		}
		return m, nil
	case "shift+tab":
		// Cycle backward
		// When maximized, skip Preview: Command → Sessions → Command...
		m.focusState = (m.focusState - 1 + 3) % 3
		if m.sessionsMaximized && m.focusState == FocusPreview {
			m.focusState = FocusSessions // Skip preview when maximized
		}
		switch m.focusState {
		case FocusSessions:
			m.statusMsg = "Focus: Sessions"
		case FocusPreview:
			m.statusMsg = "Focus: Preview"
		case FocusCommand:
			m.statusMsg = "Focus: Command"
		}
		return m, nil

	// Navigation within focused panel
	case "up", "k":
		return m.moveUp()

	case "down", "j":
		return m.moveDown()

	case "left", "h":
		return m.moveLeft()

	case "right", "l":
		return m.moveRight()

	case "pgup":
		return m.pageUp()

	case "pgdown":
		return m.pageDown()

	case "home", "g":
		return m.moveToTop()

	case "end", "G":
		return m.moveToBottom()

	// Actions
	case "enter":
		return m.selectItem()

	case "o":
		// Attach to session or create and attach from template
		return m.selectItemAndAttach()

	case "e":
		// Edit templates (Templates tab only)
		if m.sessionsTab == "templates" {
			m.statusMsg = "Opening templates in editor..."
			return m, m.editTemplatesCmd()
		}
		return m, nil

	case "s", "S":
		// Save session as template (Sessions panel only, when focused)
		if m.focusState == FocusSessions && m.sessionsTab == "sessions" && len(m.sessionTreeItems) > 0 && m.selectedSession < len(m.sessionTreeItems) {
			item := m.sessionTreeItems[m.selectedSession]
			if item.Type == "session" && item.Session != nil {
				m.statusMsg = "Extracting session '" + item.Session.Name + "'..."
				return m, m.extractSessionCmd(item.Session.Name)
			}
		}
		return m, nil

	case "r", "R":
		// Context-specific: Refresh preview OR rename session
		if m.focusState == FocusPreview {
			// Refresh preview panel when preview is focused
			m.updatePreviewContent()
			m.statusMsg = "Preview refreshed"
			return m, nil
		} else if m.focusState == FocusSessions && m.sessionsTab == "sessions" && len(m.sessionTreeItems) > 0 && m.selectedSession < len(m.sessionTreeItems) {
			// Rename session (Sessions panel only, when focused)
			item := m.sessionTreeItems[m.selectedSession]
			if item.Type == "session" && item.Session != nil {
				m.inputMode = "rename"
				m.inputBuffer = item.Session.Name // Pre-fill with current name
				m.inputPrompt = "Rename session: "
				m.renameTarget = item.Session.Name
				m.statusMsg = "Enter new name for session '" + item.Session.Name + "' (ESC to cancel)"
				return m, nil
			}
		}
		return m, nil

	case "n", "N":
		// New template (Templates tab only)
		if m.sessionsTab == "templates" {
			m.startTemplateCreation()
			return m, nil
		}
		return m, nil

	case "d", "D":
		// Detach from session (Sessions panel only, when focused)
		if m.focusState == FocusSessions && m.sessionsTab == "sessions" && len(m.sessionTreeItems) > 0 && m.selectedSession < len(m.sessionTreeItems) {
			item := m.sessionTreeItems[m.selectedSession]
			if item.Type == "session" && item.Session != nil {
				session := item.Session

				// Check if it's the current session (where conductor-tui is running)
				if session.Name == m.currentSessionName {
					m.statusMsg = "⚠️  Can't detach from current session (press q to quit)"
					return m, nil
				}

				// Check if session is attached
				if !session.Attached {
					m.statusMsg = "⚠️  Session '" + session.Name + "' is not attached"
					return m, nil
				}

				// Detach from session
				m.statusMsg = "Detaching from session: " + session.Name + "..."
				return m, m.detachSessionCmd(session.Name)
			}
		}
		return m, nil

	case "x":
		// Kill session (Sessions panel only, when focused, with confirmation)
		if m.focusState == FocusSessions && m.sessionsTab == "sessions" && len(m.sessionTreeItems) > 0 && m.selectedSession < len(m.sessionTreeItems) {
			item := m.sessionTreeItems[m.selectedSession]
			if item.Type == "session" && item.Session != nil {
				// Prompt for confirmation
				m.inputMode = "kill_confirm"
				m.inputPrompt = fmt.Sprintf("Kill session '%s'? (y/n): ", item.Session.Name)
				m.statusMsg = "Confirm kill"
				return m, nil
			}
		}
		return m, nil

	case " ": // space
		return m.toggleSelection()

	case "f", "F":
		// Cycle through session filters (Sessions tab only)
		if m.sessionsTab == "sessions" {
			switch m.sessionFilter {
			case FilterAll:
				m.sessionFilter = FilterAI
				m.statusMsg = "Filter: AI sessions only"
			case FilterAI:
				m.sessionFilter = FilterAttached
				m.statusMsg = "Filter: Attached sessions only"
			case FilterAttached:
				m.sessionFilter = FilterDetached
				m.statusMsg = "Filter: Detached sessions only"
			case FilterDetached:
				m.sessionFilter = FilterAll
				m.statusMsg = "Filter: All sessions"
			}
			// Reset selection to first item
			m.selectedSession = 0
			m.updateSessionsContent()
			return m, nil
		}
		return m, nil
	}

	return m, nil
}

// Navigation helper functions

func (m model) moveUp() (tea.Model, tea.Cmd) {
	// If preview is focused, scroll preview up instead of navigating
	if m.focusState == FocusPreview {
		if m.previewScrollOffset > 0 {
			m.previewScrollOffset--
			m.updatePreviewContent()
			m.statusMsg = fmt.Sprintf("Preview: Line %d/%d", m.previewScrollOffset+1, m.previewTotalLines)
		}
		return m, nil
	}

	// Auto-focus top panel when arrow keys pressed
	if m.focusState != FocusSessions {
		m.focusState = FocusSessions
		if m.sessionsTab == "templates" {
			m.statusMsg = "Focus: Templates (auto-switched for navigation)"
		} else {
			m.statusMsg = "Focus: Sessions (auto-switched for navigation)"
		}
	}

	// Navigate based on active tab
	if m.sessionsTab == "templates" {
		// Navigate templates tree
		if len(m.templateTreeItems) > 0 {
			m.selectedTemplate--
			if m.selectedTemplate < 0 {
				m.selectedTemplate = 0
			}
			m.previewScrollOffset = 0     // Reset scroll when changing template
			m.updateTemplatesContent()
			m.updatePreviewContent() // Update preview to show template details
			m.statusMsg = m.getContextualStatusMessage()
		}
	} else {
		// Navigate sessions tree
		if len(m.sessionTreeItems) > 0 {
			m.selectedSession--
			if m.selectedSession < 0 {
				m.selectedSession = 0
			}
			m.previewScrollOffset = 0     // Reset scroll position when changing selection
			m.autoScrolledSession = ""    // Reset auto-scroll flag when changing selection
			m.updateSessionsContent()
			m.adjustSessionsScrollToSelection() // Auto-scroll to keep selection visible
			m.updatePreviewContent()
			m.statusMsg = m.getContextualStatusMessage()
		}
	}
	return m, nil
}

func (m model) moveDown() (tea.Model, tea.Cmd) {
	// If preview is focused, scroll preview down instead of navigating
	if m.focusState == FocusPreview {
		// Calculate max scroll offset
		_, totalContentHeight := m.calculateLayout()
		totalContentHeight += 2
		_, previewHeight, _ := m.calculateAdaptivePanelHeights(totalContentHeight)
		contentHeight := previewHeight - 1 - 2 // -1 for header, -2 for borders
		if contentHeight < 1 {
			contentHeight = 1
		}
		maxOffset := m.previewTotalLines - contentHeight
		if maxOffset < 0 {
			maxOffset = 0
		}

		if m.previewScrollOffset < maxOffset {
			m.previewScrollOffset++
			m.updatePreviewContent()
			m.statusMsg = fmt.Sprintf("Preview: Line %d/%d", m.previewScrollOffset+1, m.previewTotalLines)
		}
		return m, nil
	}

	// Auto-focus top panel when arrow keys pressed
	if m.focusState != FocusSessions {
		m.focusState = FocusSessions
		if m.sessionsTab == "templates" {
			m.statusMsg = "Focus: Templates (auto-switched for navigation)"
		} else {
			m.statusMsg = "Focus: Sessions (auto-switched for navigation)"
		}
	}

	// Navigate based on active tab
	if m.sessionsTab == "templates" {
		// Navigate templates tree
		if len(m.templateTreeItems) > 0 {
			m.selectedTemplate++
			if m.selectedTemplate >= len(m.templateTreeItems) {
				m.selectedTemplate = len(m.templateTreeItems) - 1
			}
			m.previewScrollOffset = 0     // Reset scroll when changing template
			m.updateTemplatesContent()
			m.updatePreviewContent() // Update preview to show template details
			m.statusMsg = m.getContextualStatusMessage()
		}
	} else {
		// Navigate sessions tree
		if len(m.sessionTreeItems) > 0 {
			m.selectedSession++
			if m.selectedSession >= len(m.sessionTreeItems) {
				m.selectedSession = len(m.sessionTreeItems) - 1
			}
			m.previewScrollOffset = 0     // Reset scroll position when changing selection
			m.autoScrolledSession = ""    // Reset auto-scroll flag when changing selection
			m.updateSessionsContent()
			m.adjustSessionsScrollToSelection() // Auto-scroll to keep selection visible
			m.updatePreviewContent()
			m.statusMsg = m.getContextualStatusMessage()
		}
	}
	return m, nil
}

func (m model) moveLeft() (tea.Model, tea.Cmd) {
	// In Templates tab: collapse category if on a category item
	if m.sessionsTab == "templates" && len(m.templateTreeItems) > 0 && m.selectedTemplate < len(m.templateTreeItems) {
		item := m.templateTreeItems[m.selectedTemplate]
		if item.Type == "category" && m.expandedCategories[item.Name] {
			// Collapse the category
			m.expandedCategories[item.Name] = false
			m.updateTemplateTreeItems()
			m.updateTemplatesContent()
			m.updatePreviewContent() // Update preview
			m.statusMsg = "Collapsed category: " + item.Name
			return m, nil
		}
	}

	// In Sessions tab: collapse session if on a session item (or child of expanded session)
	if m.sessionsTab == "sessions" && len(m.sessionTreeItems) > 0 && m.selectedSession < len(m.sessionTreeItems) {
		item := m.sessionTreeItems[m.selectedSession]

		// If on an expanded session, collapse it
		if item.Type == "session" && m.expandedSessions[item.Session.Name] {
			m.expandedSessions[item.Session.Name] = false
			m.updateSessionTreeItems()
			m.updateSessionsContent()
			m.updatePreviewContent()
			m.statusMsg = "Collapsed session: " + item.Session.Name
			return m, nil
		}

		// If on a window/pane, collapse its parent session
		if (item.Type == "window" || item.Type == "pane") && item.Session != nil {
			if m.expandedSessions[item.Session.Name] {
				m.expandedSessions[item.Session.Name] = false

				// Find the session item in the tree to move selection there
				for i, treeItem := range m.sessionTreeItems {
					if treeItem.Type == "session" && treeItem.Session != nil && treeItem.Session.Name == item.Session.Name {
						m.selectedSession = i
						break
					}
				}

				m.updateSessionTreeItems()
				m.updateSessionsContent()
				m.updatePreviewContent()
				m.statusMsg = "Collapsed session: " + item.Session.Name
				return m, nil
			}
		}
	}

	return m, nil
}

func (m model) moveRight() (tea.Model, tea.Cmd) {
	// In Templates tab: expand category if on a category item
	if m.sessionsTab == "templates" && len(m.templateTreeItems) > 0 && m.selectedTemplate < len(m.templateTreeItems) {
		item := m.templateTreeItems[m.selectedTemplate]
		if item.Type == "category" && !m.expandedCategories[item.Name] {
			// Expand the category
			m.expandedCategories[item.Name] = true
			m.updateTemplateTreeItems()
			m.updateTemplatesContent()
			m.updatePreviewContent() // Update preview
			m.statusMsg = "Expanded category: " + item.Name
			return m, nil
		}
	}

	// In Sessions tab: expand session if on a session item
	if m.sessionsTab == "sessions" && len(m.sessionTreeItems) > 0 && m.selectedSession < len(m.sessionTreeItems) {
		item := m.sessionTreeItems[m.selectedSession]
		if item.Type == "session" && !m.expandedSessions[item.Session.Name] {
			// Don't expand single-pane sessions (they work directly without expanding)
			if item.Session.Windows == 1 {
				windows, err := listWindows(item.Session.Name)
				if err == nil && len(windows) > 0 && windows[0].Panes == 1 {
					m.statusMsg = "Single-pane session - no need to expand (use directly)"
					return m, nil
				}
			}

			// Expand the session
			m.expandedSessions[item.Session.Name] = true
			m.updateSessionTreeItems()
			m.updateSessionsContent()
			m.updatePreviewContent() // Update preview after expansion
			m.statusMsg = "Expanded session: " + item.Session.Name
			return m, nil
		}
	}

	return m, nil
}

func (m model) pageUp() (tea.Model, tea.Cmd) {
	// Handle scrolling based on current focus
	if m.focusState == FocusSessions {
		// Scroll sessions panel
		_, contentHeight := m.calculateLayout()
		contentHeight += 2 // Add back for panel height calculation
		sessionsHeight, _, _ := m.calculateAdaptivePanelHeights(contentHeight)

		pageSize := sessionsHeight - 2 // -2 for borders
		if pageSize < 1 {
			pageSize = 1
		}

		m.sessionsScrollOffset -= pageSize
		if m.sessionsScrollOffset < 0 {
			m.sessionsScrollOffset = 0
		}

		totalLines := len(m.sessionsContent)
		m.statusMsg = fmt.Sprintf("Sessions: Line %d/%d", m.sessionsScrollOffset+1, totalLines)
		return m, nil
	}

	// Auto-focus preview panel when PgUp pressed from other panels
	if m.focusState != FocusPreview {
		m.focusState = FocusPreview
		m.statusMsg = "Focus: Preview (auto-switched for scrolling)"
	}

	if len(m.previewBuffer) == 0 {
		return m, nil
	}

	// Calculate preview height
	_, contentHeight := m.calculateLayout()
	contentHeight += 2
	_, previewHeight, _ := m.calculateAdaptivePanelHeights(contentHeight)

	// Calculate page size (accounting for borders)
	pageSize := previewHeight - 2 // -2 for borders
	if pageSize < 1 {
		pageSize = 1
	}

	m.previewScrollOffset -= pageSize
	if m.previewScrollOffset < 0 {
		m.previewScrollOffset = 0
	}

	m.updatePreviewContent()
	m.statusMsg = fmt.Sprintf("Preview: Line %d/%d", m.previewScrollOffset+1, m.previewTotalLines)
	return m, nil
}

func (m model) pageDown() (tea.Model, tea.Cmd) {
	// Handle scrolling based on current focus
	if m.focusState == FocusSessions {
		// Scroll sessions panel
		_, contentHeight := m.calculateLayout()
		contentHeight += 2 // Add back for panel height calculation
		sessionsHeight, _, _ := m.calculateAdaptivePanelHeights(contentHeight)

		pageSize := sessionsHeight - 2 // -2 for borders
		if pageSize < 1 {
			pageSize = 1
		}

		totalLines := len(m.sessionsContent)
		maxOffset := totalLines - pageSize
		if maxOffset < 0 {
			maxOffset = 0
		}

		m.sessionsScrollOffset += pageSize
		if m.sessionsScrollOffset > maxOffset {
			m.sessionsScrollOffset = maxOffset
		}

		m.statusMsg = fmt.Sprintf("Sessions: Line %d/%d", m.sessionsScrollOffset+1, totalLines)
		return m, nil
	}

	// Auto-focus preview panel when PgDn pressed from other panels
	if m.focusState != FocusPreview {
		m.focusState = FocusPreview
		m.statusMsg = "Focus: Preview (auto-switched for scrolling)"
	}

	if len(m.previewBuffer) == 0 {
		return m, nil
	}

	// Calculate preview height
	_, contentHeight := m.calculateLayout()
	contentHeight += 2
	_, previewHeight, _ := m.calculateAdaptivePanelHeights(contentHeight)

	// Calculate page size (accounting for borders)
	pageSize := previewHeight - 2 // -2 for borders
	if pageSize < 1 {
		pageSize = 1
	}

	maxOffset := m.previewTotalLines - pageSize
	if maxOffset < 0 {
		maxOffset = 0
	}

	m.previewScrollOffset += pageSize
	if m.previewScrollOffset > maxOffset {
		m.previewScrollOffset = maxOffset
	}

	m.updatePreviewContent()
	m.statusMsg = fmt.Sprintf("Preview: Line %d/%d", m.previewScrollOffset+1, m.previewTotalLines)
	return m, nil
}

func (m model) moveToTop() (tea.Model, tea.Cmd) {
	// Auto-focus preview panel when Home/g pressed
	if m.focusState != FocusPreview {
		m.focusState = FocusPreview
		m.statusMsg = "Focus: Preview (auto-switched for scrolling)"
	}

	if len(m.previewBuffer) == 0 {
		return m, nil
	}

	m.previewScrollOffset = 0
	m.updatePreviewContent()
	m.statusMsg = fmt.Sprintf("Preview: Top (Line 1/%d)", m.previewTotalLines)
	return m, nil
}

func (m model) moveToBottom() (tea.Model, tea.Cmd) {
	// Auto-focus preview panel when End/G pressed
	if m.focusState != FocusPreview {
		m.focusState = FocusPreview
		m.statusMsg = "Focus: Preview (auto-switched for scrolling)"
	}

	if len(m.previewBuffer) == 0 {
		return m, nil
	}

	// Calculate preview height on Chat tab (same as in view_tabs.go)
	_, contentHeight := m.calculateLayout()
	var previewHeight int
	if contentHeight >= 30 {
		previewHeight = contentHeight * 70 / 100
	} else if contentHeight >= 20 {
		previewHeight = contentHeight * 75 / 100
	} else {
		previewHeight = contentHeight - 4 // Leave 4 lines for command panel
	}

	pageSize := previewHeight - 3 - 2 // -3 for header, -2 for borders
	if pageSize < 1 {
		pageSize = 10
	}

	maxOffset := m.previewTotalLines - pageSize
	if maxOffset < 0 {
		maxOffset = 0
	}

	m.previewScrollOffset = maxOffset
	m.updatePreviewContent()
	m.statusMsg = fmt.Sprintf("Preview: Bottom (Line %d/%d)", m.previewScrollOffset+1, m.previewTotalLines)
	return m, nil
}

// adjustSessionsScrollToSelection adjusts the sessions scroll offset to keep the selected session visible
func (m *model) adjustSessionsScrollToSelection() {
	if len(m.sessions) == 0 {
		return
	}

	// Calculate viewport size
	_, contentHeight := m.calculateLayout()
	contentHeight += 2 // Add back for panel height calculation
	sessionsHeight, _, _ := m.calculateAdaptivePanelHeights(contentHeight)
	viewportSize := sessionsHeight - 2 // -2 for borders

	if viewportSize < 1 {
		viewportSize = 1
	}

	// Find exact line position of selected item by scanning sessionsContent
	// for SELECTED: tags (applied during updateSessionsContent)
	selectionStart := -1
	selectionEnd := -1
	for i, line := range m.sessionsContent {
		if strings.Contains(line, "SELECTED:") {
			if selectionStart == -1 {
				selectionStart = i
			}
			selectionEnd = i
		} else if selectionStart != -1 {
			// Past the selected block, stop scanning
			break
		}
	}

	// Fallback if no SELECTED tag found (shouldn't happen, but be safe)
	if selectionStart == -1 {
		return
	}

	// Adjust scroll to keep the full selected item visible
	// If selection starts above viewport, scroll up
	if selectionStart < m.sessionsScrollOffset {
		m.sessionsScrollOffset = selectionStart
	}

	// If selection ends below viewport, scroll down
	if selectionEnd >= m.sessionsScrollOffset+viewportSize {
		m.sessionsScrollOffset = selectionEnd - viewportSize + 1
	}

	// Ensure scroll offset doesn't go negative
	if m.sessionsScrollOffset < 0 {
		m.sessionsScrollOffset = 0
	}

	// Ensure we don't scroll past the bottom
	totalLines := len(m.sessionsContent)
	maxOffset := totalLines - viewportSize
	if maxOffset < 0 {
		maxOffset = 0
	}
	if m.sessionsScrollOffset > maxOffset {
		m.sessionsScrollOffset = maxOffset
	}
}

// Action helper functions

func (m model) selectItem() (tea.Model, tea.Cmd) {
	// Handle selection based on current tab
	if m.sessionsTab == "sessions" && len(m.sessionTreeItems) > 0 && m.selectedSession < len(m.sessionTreeItems) {
		// Handle session tree item selection
		item := m.sessionTreeItems[m.selectedSession]

		if item.Type == "session" && item.Session != nil {
			// Attach to the selected session
			session := *item.Session

			// Check if trying to attach to the current session
			if session.Name == m.currentSessionName {
				m.statusMsg = "Already in session '" + session.Name + "' (press q to exit conductor-tui)"
				return m, nil
			}

			if m.popupMode {
				// In popup mode, switch client directly and quit
				if err := switchClient(session.Name); err != nil {
					m.statusMsg = "Failed to switch to session: " + err.Error()
					return m, nil
				}
				return m, tea.Quit
			} else {
				// In normal mode, set session to attach on exit
				m.attachOnExit = session.Name
				return m, tea.Quit
			}
		} else {
			// For window/pane items, just update preview
			m.updatePreviewContent()
			m.statusMsg = fmt.Sprintf("Viewing: %s", item.Name)
			return m, nil
		}
	} else if m.sessionsTab == "templates" && len(m.templateTreeItems) > 0 && m.selectedTemplate < len(m.templateTreeItems) {
		// Handle template tree item selection
		item := m.templateTreeItems[m.selectedTemplate]

		if item.Type == "category" {
			// Toggle category expansion
			m.expandedCategories[item.Name] = !m.expandedCategories[item.Name]

			// Update tree items and templates panel
			m.updateTemplateTreeItems()
			m.updateTemplatesContent()
			m.updatePreviewContent() // Update preview

			if m.expandedCategories[item.Name] {
				m.statusMsg = "Expanded category: " + item.Name
			} else {
				m.statusMsg = "Collapsed category: " + item.Name
			}
			return m, nil
		} else if item.Type == "template" && item.Template != nil {
			// Create session from selected template
			m.statusMsg = "Creating session from template: " + item.Template.Name + "..."
			return m, m.createSessionFromTemplateCmd(*item.Template)
		}
	}
	return m, nil
}

// selectItemAndAttach is like selectItem but creates the session and immediately attaches to it
func (m model) selectItemAndAttach() (tea.Model, tea.Cmd) {
	// For sessions, behave the same as selectItem (already attaching)
	if m.sessionsTab == "sessions" {
		return m.selectItem()
	}

	// For templates, create session and attach immediately
	if m.sessionsTab == "templates" && len(m.templateTreeItems) > 0 && m.selectedTemplate < len(m.templateTreeItems) {
		item := m.templateTreeItems[m.selectedTemplate]

		if item.Type == "category" {
			// Same behavior as selectItem for categories
			return m.selectItem()
		} else if item.Type == "template" && item.Template != nil {
			// Create session and attach immediately
			m.statusMsg = "Creating and attaching to: " + item.Template.Name + "..."
			return m, m.createSessionFromTemplateAndAttachCmd(*item.Template)
		}
	}
	return m, nil
}

// createSessionFromTemplateCmd creates a tea.Cmd to create a session asynchronously
func (m model) createSessionFromTemplateCmd(template SessionTemplate) tea.Cmd {
	return func() tea.Msg {
		sessionName, err := createSessionFromTemplate(template)
		return sessionCreatedMsg{
			sessionName: sessionName,
			err:         err,
		}
	}
}

// createSessionFromTemplateAndAttachCmd creates a session and immediately attaches to it
func (m model) createSessionFromTemplateAndAttachCmd(template SessionTemplate) tea.Cmd {
	return func() tea.Msg {
		sessionName, err := createSessionFromTemplate(template)
		return sessionCreatedAndAttachMsg{
			sessionName: sessionName,
			err:         err,
		}
	}
}

// attachToSessionCmd creates a tea.Cmd to attach to a session
func (m model) attachToSessionCmd(sessionName string) tea.Cmd {
	return func() tea.Msg {
		err := attachToSession(sessionName)
		return sessionAttachedMsg{
			sessionName: sessionName,
			err:         err,
		}
	}
}

// killSessionCmd creates a tea.Cmd to kill a session
func (m model) killSessionCmd(sessionName string) tea.Cmd {
	return func() tea.Msg {
		err := killSession(sessionName)
		return sessionKilledMsg{
			sessionName: sessionName,
			err:         err,
		}
	}
}

// detachSessionCmd creates a tea.Cmd to detach from a specific session
func (m model) detachSessionCmd(sessionName string) tea.Cmd {
	return func() tea.Msg {
		err := detachSession(sessionName)
		return sessionDetachedMsg{
			sessionName: sessionName,
			err:         err,
		}
	}
}

// detachCurrentSessionCmd creates a tea.Cmd to detach from the current session
func (m model) detachCurrentSessionCmd() tea.Cmd {
	return func() tea.Msg {
		err := detachClient()
		if err != nil {
			return errMsg{err: err}
		}
		// After detaching, quit the TUI
		return tea.Quit()
	}
}

// renameSessionCmd creates a tea.Cmd to rename a session
func (m model) renameSessionCmd(oldName, newName string) tea.Cmd {
	return func() tea.Msg {
		err := renameSession(oldName, newName)
		return sessionRenamedMsg{
			oldName: oldName,
			newName: newName,
			err:     err,
		}
	}
}

// editTemplatesCmd creates a tea.Cmd to open templates in editor
// Uses tea.ExecProcess to properly suspend/resume the TUI
func (m model) editTemplatesCmd() tea.Cmd {
	editor, args, _ := getUserEditor()
	templatesPath, err := getTemplatesPath()
	if err != nil {
		return func() tea.Msg {
			return templatesReloadedMsg{
				templates: nil,
				err:       err,
			}
		}
	}

	// Build command with args
	allArgs := append(args, templatesPath)

	// Use tea.ExecProcess to properly suspend the TUI, run the editor, and resume
	c := tea.ExecProcess(exec.Command(editor, allArgs...), func(err error) tea.Msg {
		// This callback runs after the editor exits
		if err != nil {
			return templatesReloadedMsg{
				templates: nil,
				err:       err,
			}
		}

		// Reload templates after editing
		templates, err := loadTemplates()
		return templatesReloadedMsg{
			templates: templates,
			err:       err,
		}
	})

	return c
}

// editCommandCmd creates a tea.Cmd to open command input in external editor
// Similar to Claude Code's Ctrl+G feature for editing prompts
func (m model) editCommandCmd() tea.Cmd {
	editor, args, _ := getUserEditor()

	// Create temp file with current command content
	tmpFile, err := os.CreateTemp("", "conductor-tui-cmd-*.txt")
	if err != nil {
		return func() tea.Msg {
			return commandEditedMsg{content: "", err: err}
		}
	}
	tmpPath := tmpFile.Name()

	// Write current command input to temp file
	if m.commandInput != "" {
		if _, err := tmpFile.WriteString(m.commandInput); err != nil {
			tmpFile.Close()
			os.Remove(tmpPath)
			return func() tea.Msg {
				return commandEditedMsg{content: "", err: err}
			}
		}
	}
	tmpFile.Close()

	// Build command with args
	allArgs := append(args, tmpPath)

	// Use tea.ExecProcess to properly suspend the TUI, run the editor, and resume
	c := tea.ExecProcess(exec.Command(editor, allArgs...), func(err error) tea.Msg {
		// This callback runs after the editor exits
		defer os.Remove(tmpPath) // Clean up temp file

		if err != nil {
			return commandEditedMsg{content: "", err: err}
		}

		// Read edited content from temp file
		content, err := os.ReadFile(tmpPath)
		if err != nil {
			return commandEditedMsg{content: "", err: err}
		}

		// Trim trailing newline that editors typically add
		text := strings.TrimSuffix(string(content), "\n")
		text = strings.TrimSuffix(text, "\r\n")

		return commandEditedMsg{content: text, err: nil}
	})

	return c
}

func (m model) toggleSelection() (tea.Model, tea.Cmd) {
	// Implement toggle selection
	return m, nil
}

func (m model) switchFocus() (tea.Model, tea.Cmd) {
	// Implement focus switching between components
	return m, nil
}

func (m model) showHelp() (tea.Model, tea.Cmd) {
	// Show help dialog
	m.statusMsg = "Help: q=quit, ?=help, ↑↓=navigate, enter=select"
	return m, nil
}

func (m model) refresh() (tea.Model, tea.Cmd) {
	// Refresh the current view
	m.statusMsg = "Refreshed"
	return m, nil
}

// getContextualStatusMessage returns context-aware hotkey hints based on focus state
func (m model) getContextualStatusMessage() string {
	// Unified view: return help based on what's focused
	switch m.focusState {
	case FocusSessions:
		if len(m.sessions) > 0 {
			if m.currentSessionName != "" && m.popupMode {
				return "Sessions: [Enter] Switch | [X] Fullscreen | [ESC/q] Close popup | [s] Save | [r] Rename | [d] Detach | [x] Kill | [↑↓] Navigate"
			}
			return "Sessions: [Enter] Attach | [s] Save as template | [r] Rename | [d] Detach | [x] Kill | [↑↓] Navigate | [Ctrl+R] Refresh | [q] Quit"
		}
		return "Sessions: No active sessions | [3] Templates | [q] Quit"
	case FocusPreview:
		hasWindows := len(m.windows) > 1
		hasScrollableContent := len(m.previewBuffer) > 0
		if hasWindows && hasScrollableContent {
			return fmt.Sprintf("Preview: [←→] Windows (%d/%d) | [PgUp/PgDn] Scroll | [r] Refresh | [Home/End] Top/Bottom | [Tab] Cycle focus | [q] Quit", m.selectedWindow+1, len(m.windows))
		} else if hasWindows {
			return fmt.Sprintf("Preview: [←→] Windows (%d/%d) | [r] Refresh | [Tab] Cycle focus | [q] Quit", m.selectedWindow+1, len(m.windows))
		} else if hasScrollableContent {
			return "Preview: [PgUp/PgDn] Scroll | [r] Refresh | [Home/End] Top/Bottom | [Tab] Cycle focus | [q] Quit"
		}
		return "Preview: [r] Refresh | [Tab] Cycle focus | [q] Quit"
	case FocusCommand:
		if len(m.sessions) > 0 {
			selectedSession := m.sessions[m.selectedSession]
			return fmt.Sprintf("Command: Type to send to '%s' | [Enter] Send | [Esc] Clear | [↑↓] History | [Tab] Cycle focus", selectedSession.Name)
		}
		return "Command: [Tab] Cycle focus | [q] Quit"
	default:
		return "Navigate: [1-2] Focus | [Tab/Shift+Tab] Cycle | [↑↓] Navigate | [q] Quit"
	}
}

// Key bindings definition
type keyMap struct {
	Quit    key.Binding
	Help    key.Binding
	Refresh key.Binding
	Up      key.Binding
	Down    key.Binding
	Left    key.Binding
	Right   key.Binding
	Select  key.Binding
	Toggle  key.Binding
}

var keys = keyMap{
	Quit: key.NewBinding(
		key.WithKeys("q", "ctrl+c"),
		key.WithHelp("q", "quit"),
	),
	Help: key.NewBinding(
		key.WithKeys("?"),
		key.WithHelp("?", "help"),
	),
	Refresh: key.NewBinding(
		key.WithKeys("ctrl+r"),
		key.WithHelp("ctrl+r", "refresh"),
	),
	Up: key.NewBinding(
		key.WithKeys("up", "k"),
		key.WithHelp("↑/k", "up"),
	),
	Down: key.NewBinding(
		key.WithKeys("down", "j"),
		key.WithHelp("↓/j", "down"),
	),
	Left: key.NewBinding(
		key.WithKeys("left", "h"),
		key.WithHelp("←/h", "left"),
	),
	Right: key.NewBinding(
		key.WithKeys("right", "l"),
		key.WithHelp("→/l", "right"),
	),
	Select: key.NewBinding(
		key.WithKeys("enter"),
		key.WithHelp("enter", "select"),
	),
	Toggle: key.NewBinding(
		key.WithKeys(" "),
		key.WithHelp("space", "toggle"),
	),
}

// Template creation wizard functions

// startTemplateCreation initializes the template creation wizard
func (m *model) startTemplateCreation() {
	m.templateCreationMode = true
	m.templateBuilder = TemplateBuilder{
		step:       0,
		fieldName:  "name",
		workingDir: "~", // Default
		category:   "",  // Will be set in wizard
		panes:      []PaneTemplate{},
	}
	m.inputBuffer = ""
	m.statusMsg = "Creating new template... (ESC to cancel)"
}

// handleTemplateCreationInput handles keyboard input during template creation wizard
func (m model) handleTemplateCreationInput(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.Type {
	case tea.KeyEsc:
		// Cancel wizard
		m.templateCreationMode = false
		m.templateBuilder = TemplateBuilder{}
		m.inputBuffer = ""
		m.statusMsg = "Template creation cancelled"
		return m, nil

	case tea.KeyEnter:
		// Advance to next field
		return m.advanceTemplateWizard()

	case tea.KeyBackspace:
		// Remove last character
		if len(m.inputBuffer) > 0 {
			m.inputBuffer = m.inputBuffer[:len(m.inputBuffer)-1]
		}
		return m, nil

	case tea.KeySpace:
		// Handle space bar explicitly
		m.inputBuffer += " "
		return m, nil

	case tea.KeyRunes:
		// Add typed characters
		m.inputBuffer += string(msg.Runes)
		return m, nil
	}

	return m, nil
}

// advanceTemplateWizard moves to the next step in the wizard or saves the template
func (m model) advanceTemplateWizard() (tea.Model, tea.Cmd) {
	builder := &m.templateBuilder

	switch builder.fieldName {
	case "name":
		if m.inputBuffer == "" {
			m.statusMsg = "Template name cannot be empty"
			return m, nil
		}
		builder.name = m.inputBuffer
		m.inputBuffer = ""
		builder.fieldName = "description"
		m.statusMsg = "Step 2/7: Enter template description (press Enter to skip)"

	case "description":
		builder.description = m.inputBuffer
		m.inputBuffer = "" // Start empty for category selection
		builder.fieldName = "category"
		m.statusMsg = "Step 3/7: Enter category (Projects, Agents, Tools, Custom, or type your own)"

	case "category":
		// Default to "Uncategorized" if empty
		if m.inputBuffer == "" {
			builder.category = "Uncategorized"
		} else {
			builder.category = m.inputBuffer
		}
		m.inputBuffer = builder.workingDir // Pre-fill with default
		builder.fieldName = "working_dir"
		m.statusMsg = "Step 4/7: Enter working directory (e.g., ~/projects/myapp)"

	case "working_dir":
		if m.inputBuffer == "" {
			m.inputBuffer = "~" // Default to home
		}
		builder.workingDir = m.inputBuffer
		m.inputBuffer = ""
		builder.fieldName = "layout"
		m.statusMsg = "Step 5/7: Enter layout (e.g., 2x2, 3x3, 4x2)"

	case "layout":
		if m.inputBuffer == "" {
			m.statusMsg = "Layout cannot be empty (e.g., 2x2)"
			return m, nil
		}
		// TODO: Validate layout format (e.g., "2x2", "3x3")
		builder.layout = m.inputBuffer
		builder.numPanes = calculatePaneCount(m.inputBuffer)
		m.inputBuffer = ""
		builder.currentPane = 0
		builder.fieldName = "pane_command"
		m.statusMsg = fmt.Sprintf("Step 6/%d: Pane %d command (e.g., nvim, bash)", 6+builder.numPanes*2, builder.currentPane+1)

	case "pane_command":
		// Store command for current pane
		if builder.currentPane >= len(builder.panes) {
			builder.panes = append(builder.panes, PaneTemplate{})
		}
		builder.panes[builder.currentPane].Command = m.inputBuffer
		m.inputBuffer = ""
		builder.fieldName = "pane_title"
		m.statusMsg = fmt.Sprintf("Step %d/%d: Pane %d title (optional, press Enter to skip)", 6+builder.currentPane*2+1, 6+builder.numPanes*2, builder.currentPane+1)

	case "pane_title":
		// Store title for current pane
		builder.panes[builder.currentPane].Title = m.inputBuffer
		m.inputBuffer = ""
		builder.currentPane++

		// Check if we need more panes
		if builder.currentPane < builder.numPanes {
			builder.fieldName = "pane_command"
			m.statusMsg = fmt.Sprintf("Step %d/%d: Pane %d command", 6+builder.currentPane*2, 6+builder.numPanes*2, builder.currentPane+1)
		} else {
			// All panes configured, save template
			return m.saveNewTemplate()
		}

	case "pane_working_dir":
		// Optional per-pane working directory
		builder.panes[builder.currentPane].WorkingDir = m.inputBuffer
		m.inputBuffer = ""
		builder.currentPane++

		if builder.currentPane < builder.numPanes {
			builder.fieldName = "pane_command"
			m.statusMsg = fmt.Sprintf("Step %d/%d: Pane %d command", 6+builder.currentPane*3, 6+builder.numPanes*3, builder.currentPane+1)
		} else {
			return m.saveNewTemplate()
		}
	}

	return m, nil
}

// saveNewTemplate creates and saves the new template
func (m model) saveNewTemplate() (tea.Model, tea.Cmd) {
	builder := m.templateBuilder

	template := SessionTemplate{
		Name:        builder.name,
		Description: builder.description,
		Category:    builder.category,
		WorkingDir:  builder.workingDir,
		Layout:      builder.layout,
		Panes:       builder.panes,
	}

	// Exit wizard mode
	m.templateCreationMode = false
	m.templateBuilder = TemplateBuilder{}
	m.inputBuffer = ""
	m.statusMsg = "Saving template..."

	return m, m.saveTemplateCmd(template)
}

// calculatePaneCount calculates the number of panes from layout string (e.g., "2x2" = 4)
func calculatePaneCount(layout string) int {
	var rows, cols int
	fmt.Sscanf(layout, "%dx%d", &cols, &rows)
	if rows == 0 || cols == 0 {
		return 4 // Default to 2x2
	}
	return rows * cols
}

// saveTemplateCmd creates a tea.Cmd to save a template
func (m model) saveTemplateCmd(template SessionTemplate) tea.Cmd {
	return func() tea.Msg {
		err := addTemplate(template)
		return templateSavedMsg{
			template: template,
			err:      err,
		}
	}
}

// deleteTemplateCmd creates a tea.Cmd to delete a template
func (m model) deleteTemplateCmd(index int) tea.Cmd {
	return func() tea.Msg {
		err := deleteTemplate(index)
		return templateDeletedMsg{
			templateIndex: index,
			err:           err,
		}
	}
}

// extractSessionCmd creates a tea.Cmd to extract session info for saving as template
func (m model) extractSessionCmd(sessionName string) tea.Cmd {
	return func() tea.Msg {
		info, err := extractSessionInfo(sessionName)
		return sessionExtractedMsg{
			sessionName: sessionName,
			info:        info,
			err:         err,
		}
	}
}

// handleSessionSaveInput handles keyboard input during session save mode
func (m model) handleSessionSaveInput(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.Type {
	case tea.KeyEsc:
		// Cancel save
		m.sessionSaveMode = false
		m.sessionBuilder = SessionSaveBuilder{}
		m.inputBuffer = ""
		m.statusMsg = "Save cancelled"
		return m, nil

	case tea.KeyEnter:
		// Advance to next field or save
		return m.advanceSessionSave()

	case tea.KeyBackspace:
		// Remove last character
		if len(m.inputBuffer) > 0 {
			m.inputBuffer = m.inputBuffer[:len(m.inputBuffer)-1]
		}
		return m, nil

	case tea.KeySpace:
		// Handle space bar explicitly
		m.inputBuffer += " "
		return m, nil

	case tea.KeyRunes:
		// Add typed characters
		m.inputBuffer += string(msg.Runes)
		return m, nil
	}

	return m, nil
}

// advanceSessionSave advances the session save wizard or saves the template
func (m model) advanceSessionSave() (tea.Model, tea.Cmd) {
	builder := &m.sessionBuilder

	switch builder.fieldName {
	case "name":
		if m.inputBuffer == "" {
			m.statusMsg = "Template name cannot be empty"
			return m, nil
		}
		builder.name = m.inputBuffer
		m.inputBuffer = ""
		builder.fieldName = "category"
		m.statusMsg = "Step 2/3: Enter category (Projects, Agents, Tools, Custom, or type your own)"
		return m, nil

	case "category":
		// Default to "Uncategorized" if empty
		if m.inputBuffer == "" {
			builder.category = "Uncategorized"
		} else {
			builder.category = m.inputBuffer
		}
		m.inputBuffer = ""
		builder.fieldName = "description"
		m.statusMsg = "Step 3/3: Enter description (optional, press Enter to skip)"
		return m, nil

	case "description":
		builder.description = m.inputBuffer
		m.inputBuffer = ""

		// Create template from builder
		template := SessionTemplate{
			Name:        builder.name,
			Description: builder.description,
			Category:    builder.category,
			WorkingDir:  builder.commonWorkDir,
			Layout:      builder.layout,
			Panes:       builder.panes,
		}

		// Exit save mode
		m.sessionSaveMode = false
		m.sessionBuilder = SessionSaveBuilder{}
		m.statusMsg = "Saving template..."

		return m, m.saveTemplateCmd(template)
	}

	return m, nil
}

// getSessionSavePrompt returns the appropriate prompt for the current save step
func (m model) getSessionSavePrompt() string {
	builder := m.sessionBuilder

	switch builder.fieldName {
	case "name":
		return fmt.Sprintf("Save '%s' as template - Step 1/3: Template name: ", builder.sessionName)
	case "category":
		return "Step 2/3: Category: "
	case "description":
		return "Step 3/3: Description (optional): "
	default:
		return "Save Session: "
	}
}

// executeCommand executes the command from command mode
func (m model) executeCommand() (tea.Model, tea.Cmd) {
	// Get the currently selected tree item
	if len(m.sessionTreeItems) == 0 || m.selectedSession >= len(m.sessionTreeItems) {
		m.statusMsg = "No session selected"
		return m, nil
	}

	item := m.sessionTreeItems[m.selectedSession]
	if item.Session == nil {
		m.statusMsg = "No session selected"
		return m, nil
	}

	targetSession := *item.Session

	// Safety check: only allow sending to specific panes OR single-pane sessions
	if item.Type == "pane" && item.Pane != nil {
		// Explicit pane selection - always allowed
	} else if item.Type == "session" && targetSession.Windows == 1 {
		// Single-window session - check if it's truly single-pane
		windows, err := listWindows(targetSession.Name)
		if err != nil || len(windows) == 0 {
			m.statusMsg = "⚠️  Failed to get window info - try expanding session first"
			return m, nil
		}
		if windows[0].Panes != 1 {
			m.statusMsg = "⚠️  Session has multiple panes - expand with → and select a specific pane"
			return m, nil
		}
		// Single pane session - we can send to it safely
	} else {
		m.statusMsg = "⚠️  Please select a specific pane to send commands to (expand session with → and select a pane)"
		return m, nil
	}

	command := m.commandInput

	// Add to history (avoid duplicates of last command)
	if len(m.commandHistory) == 0 || m.commandHistory[len(m.commandHistory)-1] != command {
		m.commandHistory = append(m.commandHistory, command)
		// Limit history to last 100 commands
		if len(m.commandHistory) > 100 {
			m.commandHistory = m.commandHistory[1:]
		}
	}

	// Update last command info
	m.lastCommand = command
	if item.Pane != nil {
		m.lastCommandTarget = fmt.Sprintf("%s (pane %d)", targetSession.Name, item.Pane.Index)
	} else {
		m.lastCommandTarget = targetSession.Name
	}
	m.lastCommandTime = "just now"

	// Clear command input
	m.commandInput = ""
	m.commandCursor = 0
	m.historyIndex = -1

	// Return to Sessions tab
	m.focusState = FocusSessions

	// Update header to show last command
	m.updateCommandContent()

	// Send the command
	if item.Pane != nil {
		// Send to the specific selected pane
		m.statusMsg = fmt.Sprintf("Sending '%s' to %s (pane %d)...", command, targetSession.Name, item.Pane.Index)
		return m, m.sendCommandToPaneCmd(item.Pane.ID, targetSession.Name, command)
	} else {
		// Single-pane session - send to session (which has only one pane)
		m.statusMsg = fmt.Sprintf("Sending '%s' to %s...", command, targetSession.Name)
		return m, m.sendCommandCmd(targetSession.Name, command)
	}
}

// sendCommandCmd creates a command to send keys to a session
func (m model) sendCommandCmd(sessionName, command string) tea.Cmd {
	return func() tea.Msg {
		err := sendKeysToSession(sessionName, command)
		if err != nil {
			return commandSentMsg{err: err}
		}
		return commandSentMsg{success: true, sessionName: sessionName, command: command}
	}
}

// sendCommandToPaneCmd creates a command to send keys to a specific pane
func (m model) sendCommandToPaneCmd(paneID, sessionName, command string) tea.Cmd {
	return func() tea.Msg {
		err := sendKeysToPane(paneID, command)
		if err != nil {
			return commandSentMsg{err: err}
		}
		return commandSentMsg{success: true, sessionName: sessionName, command: command}
	}
}

// commandSentMsg is sent when a command has been sent to a session
type commandSentMsg struct {
	success     bool
	sessionName string
	command     string
	err         error
}
