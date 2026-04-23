package main

import (
	"fmt"

	tea "github.com/charmbracelet/bubbletea"
)

// update_mouse.go - Mouse Event Handling
// Purpose: All mouse input processing
// When to extend: Add new mouse interactions or clickable elements here

// handleMouseEvent handles mouse input
func (m model) handleMouseEvent(msg tea.MouseMsg) (tea.Model, tea.Cmd) {
	if !m.config.UI.MouseEnabled {
		return m, nil
	}

	switch msg.Type {
	case tea.MouseLeft:
		return m.handleLeftClick(msg)

	case tea.MouseRight:
		return m.handleRightClick(msg)

	case tea.MouseWheelUp:
		return m.handleWheelUp(msg)

	case tea.MouseWheelDown:
		return m.handleWheelDown(msg)

	case tea.MouseMotion:
		// Handle mouse motion if needed (for hover effects)
		return m.handleMouseMotion(msg)
	}

	return m, nil
}

// handleLeftClick handles left mouse button clicks
func (m model) handleLeftClick(msg tea.MouseMsg) (tea.Model, tea.Cmd) {
	x, y := msg.X, msg.Y

	// Check for footer click (toggle scrolling) - status bar is the footer
	if m.config.UI.ShowStatus {
		footerStartY := m.height - 2 // Footer is last 2 lines
		if y >= footerStartY {
			// Toggle footer scrolling
			m.footerScrolling = !m.footerScrolling
			if m.footerScrolling {
				// Start scrolling animation
				m.footerOffset = 0 // Reset offset when starting
				return m, footerTick()
			}
			// If stopping, just return without scheduling tick
			return m, nil
		}
	}

	// Check if clicked on UI elements
	if m.isInTitleBar(x, y) {
		return m.handleTitleBarClick(x, y)
	}

	if m.isInStatusBar(x, y) {
		return m.handleStatusBarClick(x, y)
	}

	// Handle clicks in the 3-panel vertical stack
	return m.handleUnifiedPanelClick(msg)
}

// handleUnifiedPanelClick handles clicks in the unified 3-panel layout
// Uses TFE-style approach: calculate relative Y position from pane area start
func (m model) handleUnifiedPanelClick(msg tea.MouseMsg) (tea.Model, tea.Cmd) {
	x, y := msg.X, msg.Y
	_ = x // Not needed for vertical stack detection

	// Header and footer line counts (matches TFE approach)
	headerLines := 0
	if m.config.UI.ShowTitle {
		headerLines = 1
	}
	footerLines := 0
	if m.config.UI.ShowStatus {
		footerLines = 2 // Status bar is now 2 lines (status + help)
	}

	// Check if click is in pane area (not header or status bar)
	if y < headerLines || y >= m.height-footerLines {
		return m, nil // Click in header or footer
	}

	// Calculate Y position relative to pane area start (TFE approach)
	paneY := y - headerLines

	// Calculate available height for all 3 panels (matches TFE)
	totalAvailable := m.height - headerLines - footerLines

	// Calculate panel heights (matches calculateAdaptivePanelHeights logic)
	// Static layout: equal top panels, 5-line command panel (3 content + 2 borders)
	// Heights INCLUDE borders since renderDynamicPanel subtracts them
	commandHeight := 5

	// Remaining height split between sessions and preview (or all to sessions when maximized)
	remaining := totalAvailable - commandHeight

	var sessionsHeight, previewHeight int
	if m.sessionsMaximized {
		// Maximized: sessions takes all remaining space
		sessionsHeight = remaining
		previewHeight = 0
	} else {
		// Normal: split equally
		sessionsHeight = remaining / 2
		previewHeight = remaining - sessionsHeight
	}

	// Panel boundaries (cumulative heights including borders):
	// Sessions: 0 to sessionsHeight
	// Preview: sessionsHeight to (sessionsHeight + previewHeight) [if not maximized]
	// Command: (sessionsHeight + previewHeight) to end
	sessionsTotal := sessionsHeight
	previewTotal := sessionsTotal + previewHeight

	// Determine which panel was clicked (TFE-style simple comparison)
	oldFocus := m.focusState

	var focusName string
	if paneY < sessionsTotal {
		// Click in Sessions panel
		m.focusState = FocusSessions
		if m.sessionsTab == "templates" {
			focusName = "Templates"
		} else {
			focusName = "Sessions"
		}
	} else if !m.sessionsMaximized && paneY < previewTotal {
		// Click in Preview panel (only if not maximized)
		m.focusState = FocusPreview
		focusName = "Preview"
	} else {
		// Click in Command panel (everything below sessions/preview)
		m.focusState = FocusCommand
		focusName = "Command"
		if oldFocus != FocusCommand {
			m.updateCommandContent() // Update command panel when focused
		}
	}

	// Set focus status message
	m.statusMsg = "Focus: " + focusName

	// DEBUG: Uncomment to see exact boundaries during testing
	// m.statusMsg = fmt.Sprintf("paneY:%d | S:0-%d P:%d-%d C:%d+ | %s",
	// 	paneY, sessionsTotal-1, sessionsTotal, previewTotal-1, previewTotal, focusName)

	return m, nil
}

// handleRightClick handles right mouse button clicks
func (m model) handleRightClick(msg tea.MouseMsg) (tea.Model, tea.Cmd) {
	x, y := msg.X, msg.Y

	// Example: show context menu
	// return m.showContextMenu(x, y)

	_ = x
	_ = y
	return m, nil
}

// handleWheelUp handles mouse wheel scroll up
func (m model) handleWheelUp(msg tea.MouseMsg) (tea.Model, tea.Cmd) {
	// Allow scrolling preview when preview or command panel is focused
	if (m.focusState == FocusPreview || m.focusState == FocusCommand) && len(m.previewBuffer) > 0 {
		m.previewScrollOffset--
		if m.previewScrollOffset < 0 {
			m.previewScrollOffset = 0
		}
		m.updatePreviewContent()
		m.statusMsg = fmt.Sprintf("Preview: Line %d/%d", m.previewScrollOffset+1, m.previewTotalLines)
		return m, nil
	}

	// Settings tab: scroll the settings cursor, not the sessions list.
	if m.focusState == FocusSessions && m.sessionsTab == "settings" {
		if m.settingsCursor > 0 {
			m.settingsCursor--
			m.updateSettingsContent()
			m.adjustSettingsScrollToCursor()
		}
		return m, nil
	}

	// Otherwise, scroll the sessions list
	return m.moveUp()
}

// handleWheelDown handles mouse wheel scroll down
func (m model) handleWheelDown(msg tea.MouseMsg) (tea.Model, tea.Cmd) {
	// Allow scrolling preview when preview or command panel is focused
	if (m.focusState == FocusPreview || m.focusState == FocusCommand) && len(m.previewBuffer) > 0 {
		_, contentHeight := m.calculateLayout()

		// Add back the 2 lines that calculateLayout() subtracted for borders
		contentHeight += 2

		// Calculate preview height based on focus state
		sessionsHeight, previewHeight, _ := m.calculateAdaptivePanelHeights(contentHeight)
		_ = sessionsHeight // Not needed here

		// Calculate page size (accounting for header lines and borders)
		pageSize := previewHeight - 3 - 2 // -3 for header, -2 for borders
		if pageSize < 1 {
			pageSize = 1
		}
		maxOffset := m.previewTotalLines - pageSize
		if maxOffset < 0 {
			maxOffset = 0
		}

		m.previewScrollOffset++
		if m.previewScrollOffset > maxOffset {
			m.previewScrollOffset = maxOffset
		}
		m.updatePreviewContent()

		// Show position indicator
		position := ""
		if m.previewScrollOffset == 0 {
			position = " [TOP]"
		} else if m.previewScrollOffset >= maxOffset {
			position = " [BOTTOM]"
		}
		m.statusMsg = fmt.Sprintf("Preview: Line %d/%d%s", m.previewScrollOffset+1, m.previewTotalLines, position)
		return m, nil
	}

	// Settings tab: scroll the settings cursor, not the sessions list.
	if m.focusState == FocusSessions && m.sessionsTab == "settings" {
		if m.settingsCursor < m.settingsSectionCursorCount()-1 {
			m.settingsCursor++
			m.updateSettingsContent()
			m.adjustSettingsScrollToCursor()
		}
		return m, nil
	}

	// Otherwise, scroll the sessions list
	return m.moveDown()
}

// handleMouseMotion handles mouse movement (for hover effects)
func (m model) handleMouseMotion(msg tea.MouseMsg) (tea.Model, tea.Cmd) {
	// Example: highlight hovered item
	// x, y := msg.X, msg.Y
	// if m.isInItemList(x, y) {
	//     m.hoveredItem = m.getItemIndexAt(y)
	// }
	return m, nil
}

// Helper functions for click region detection

func (m model) isInTitleBar(x, y int) bool {
	if !m.config.UI.ShowTitle {
		return false
	}
	return y < 2
}

func (m model) isInStatusBar(x, y int) bool {
	if !m.config.UI.ShowStatus {
		return false
	}
	return y >= m.height-1
}

func (m model) handleTitleBarClick(x, y int) (tea.Model, tea.Cmd) {
	// Example: click on breadcrumb navigation
	// or click on window control buttons
	_ = x
	_ = y
	return m, nil
}

func (m model) handleStatusBarClick(x, y int) (tea.Model, tea.Cmd) {
	// Example: click on status bar items
	_ = x
	_ = y
	return m, nil
}

// Double-click detection (if needed)
type clickTracker struct {
	lastClickX    int
	lastClickY    int
	lastClickTime int64
}

var tracker clickTracker

func (m model) isDoubleClick(msg tea.MouseMsg) bool {
	// Implement double-click detection
	// Compare with tracker.lastClickTime
	// Reset tracker.lastClickX, tracker.lastClickY, tracker.lastClickTime
	return false
}
