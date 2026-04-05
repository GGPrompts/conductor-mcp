package main

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// view.go - View Rendering
// Purpose: Top-level view rendering and layout
// When to extend: Add new view modes or modify layout logic

// View renders the entire application
func (m model) View() string {
	// Check if terminal size is sufficient
	if !m.isValidSize() {
		return m.renderMinimalView()
	}

	// Handle errors
	if m.err != nil {
		return m.renderErrorView()
	}

	// Render unified 3-panel layout (sessions + preview + command)
	return m.renderUnifiedView()
}

// renderSinglePane renders a single-pane layout
func (m model) renderSinglePane() string {
	var sections []string

	// Title bar
	if m.config.UI.ShowTitle {
		sections = append(sections, m.renderTitleBar())
	}

	// Main content
	sections = append(sections, m.renderMainContent())

	// Status bar
	if m.config.UI.ShowStatus {
		sections = append(sections, m.renderStatusBar())
	}

	return lipgloss.JoinVertical(lipgloss.Left, sections...)
}

// renderDualPane renders a dual-pane layout (side-by-side)
func (m model) renderDualPane() string {
	var sections []string

	// Title bar
	if m.config.UI.ShowTitle {
		sections = append(sections, m.renderTitleBar())
	}

	// Calculate pane dimensions
	leftWidth, rightWidth := m.calculateDualPaneLayout()

	// Left pane
	leftPane := m.renderLeftPane(leftWidth)

	// Divider
	divider := ""
	if m.config.Layout.ShowDivider {
		divider = m.renderDivider()
	}

	// Right pane
	rightPane := m.renderRightPane(rightWidth)

	// Join panes horizontally
	panes := lipgloss.JoinHorizontal(lipgloss.Top, leftPane, divider, rightPane)
	sections = append(sections, panes)

	// Status bar
	if m.config.UI.ShowStatus {
		sections = append(sections, m.renderStatusBar())
	}

	return lipgloss.JoinVertical(lipgloss.Left, sections...)
}

// renderMultiPanel renders a multi-panel layout
func (m model) renderMultiPanel() string {
	// Implement multi-panel layout
	// This is a placeholder - customize based on your needs
	return m.renderSinglePane()
}


// Component rendering functions

// renderTitleBar renders the title bar
func (m model) renderTitleBar() string {
	title := titleStyle.Render("Tmuxplexer")
	padding := m.width - lipgloss.Width(title)
	if padding < 0 {
		padding = 0
	}
	return title + strings.Repeat(" ", padding)
}

// renderStatusBar renders the status bar
func (m model) renderStatusBar() string {
	var line1, line2 string

	// Line 1: Current status message or input prompt
	if m.sessionSaveMode {
		// Show session save wizard prompt
		line1 = m.getSessionSavePrompt() + m.inputBuffer + "█"
	} else if m.inputMode == "rename" {
		line1 = m.inputPrompt + m.inputBuffer + "█" // Show cursor
	} else if m.inputMode == "kill_confirm" {
		// Kill confirmation - make it prominent
		line1 = "⚠️  " + m.inputPrompt + " [Press Y to confirm, N to cancel]"
	} else if m.inputMode == "template_delete_confirm" {
		// Template delete confirmation
		line1 = "⚠️  " + m.inputPrompt + " [Press Y to confirm, N to cancel]"
	} else if m.templateCreationMode {
		// Show wizard input prompt
		line1 = m.getTemplateWizardPrompt() + m.inputBuffer + "█"
	} else {
		line1 = m.statusMsg
	}

	// Use scrolling footer (click to activate) or truncate if too long
	maxLen := m.width - 4
	if maxLen > 0 {
		line1 = m.renderScrollingFooter(line1, maxLen)
	}

	// Pad line1 to full width
	padding1 := m.width - visualWidth(line1)
	if padding1 < 0 {
		padding1 = 0
	}
	line1 = line1 + strings.Repeat(" ", padding1)

	// Line 2: Context-aware help text
	line2 = m.getStatusBarHelpText()

	// Use scrolling footer (click to activate) or truncate if too long
	if maxLen > 0 {
		line2 = m.renderScrollingFooter(line2, maxLen)
	}

	// Pad line2 to full width
	padding2 := m.width - visualWidth(line2)
	if padding2 < 0 {
		padding2 = 0
	}
	line2 = line2 + strings.Repeat(" ", padding2)

	// Combine both lines - use warning style for confirmations
	var line1Styled string
	if m.inputMode == "kill_confirm" || m.inputMode == "template_delete_confirm" {
		// Use warning style but with status bar padding
		line1Styled = warningStyle.Copy().Padding(0, 1).Render(line1)
	} else {
		line1Styled = statusStyle.Render(line1)
	}
	return line1Styled + "\n" + statusStyle.Render(line2)
}

// getStatusBarHelpText returns context-aware help text for the status bar
// This is now minimal since each panel shows its own contextual help
func (m model) getStatusBarHelpText() string {
	tier := m.widthTier()

	if tier == "minimal" {
		return "[1/2/3] Panels [q] Quit"
	}

	var helpParts []string

	// Show panel switching keys and global actions
	helpParts = append(helpParts, "[1/2/3] Panels", "[Tab] Cycle")

	// Add maximize toggle hint
	if m.sessionsMaximized {
		helpParts = append(helpParts, "[z] Restore")
	} else {
		helpParts = append(helpParts, "[z] Maximize")
	}

	if tier == "compact" {
		helpParts = append(helpParts, "[q] Quit")
	} else {
		helpParts = append(helpParts, "[Ctrl+R] Refresh", "[q] Quit")
	}

	return strings.Join(helpParts, " │ ")
}

// getContextualPanelHelp returns help text specific to a panel
// This is shown in the footer of each panel when focused
func (m model) getContextualPanelHelp(panelName string) string {
	tier := m.widthTier()

	// Minimal: no help line at all
	if tier == "minimal" {
		return ""
	}

	// Compact: short help
	if tier == "compact" {
		switch panelName {
		case "sessions":
			return "[↑↓] Nav [Enter] Go [f] Filter"
		case "templates":
			return "[↑↓] Nav [Enter] Create [n] New"
		case "preview":
			return "[↑↓/PgUp/PgDn] Scroll [r] Refresh"
		case "command":
			return "[Enter] Send [Esc] Clear [↑↓] History"
		default:
			return ""
		}
	}

	// Full: verbose help
	switch panelName {
	case "sessions":
		return "[↑↓] Navigate │ [Enter] Attach │ [s] Save │ [d] Detach │ [x] Kill │ [f] Filter │ [1] Templates"
	case "templates":
		return "[↑↓] Navigate │ [Enter] Create │ [n] New │ [e] Edit │ [d] Delete │ [←→] Expand │ [1] Sessions"
	case "preview":
		return "[↑↓/PgUp/PgDn] Scroll │ [g/G] Top/Bottom │ [r] Refresh"
	case "command":
		return "[Enter] Send │ [Esc] Clear │ [↑↓] History │ [Ctrl+G] Editor │ [Ctrl+V] Paste"
	default:
		return ""
	}
}

// getTemplateWizardPrompt returns the appropriate prompt for the current wizard step
func (m model) getTemplateWizardPrompt() string {
	builder := m.templateBuilder

	switch builder.fieldName {
	case "name":
		return "Step 1/7: Template name: "
	case "description":
		return "Step 2/7: Description (optional): "
	case "category":
		return "Step 3/7: Category (Projects, Agents, Tools, Custom): "
	case "working_dir":
		return "Step 4/7: Working directory: "
	case "layout":
		return "Step 5/7: Layout (e.g., 2x2, 3x3, 4x2): "
	case "pane_command":
		return lipgloss.NewStyle().Render(
			lipgloss.JoinVertical(lipgloss.Left,
				m.getWizardProgressBar(),
				"",
				"Pane "+string(rune('1'+builder.currentPane))+" command: ",
			),
		)
	case "pane_title":
		return lipgloss.NewStyle().Render(
			lipgloss.JoinVertical(lipgloss.Left,
				m.getWizardProgressBar(),
				"",
				"Pane "+string(rune('1'+builder.currentPane))+" title (optional): ",
			),
		)
	case "pane_working_dir":
		return lipgloss.NewStyle().Render(
			lipgloss.JoinVertical(lipgloss.Left,
				m.getWizardProgressBar(),
				"",
				"Pane "+string(rune('1'+builder.currentPane))+" working dir (optional): ",
			),
		)
	default:
		return "Template Wizard: "
	}
}

// getWizardProgressBar returns a progress indicator for the wizard
func (m model) getWizardProgressBar() string {
	builder := m.templateBuilder
	totalSteps := 5 + builder.numPanes*2 // name, desc, category, dir, layout + (command, title) per pane
	currentStep := 5 // Base steps completed

	// Calculate current step based on field
	switch builder.fieldName {
	case "name":
		currentStep = 1
	case "description":
		currentStep = 2
	case "category":
		currentStep = 3
	case "working_dir":
		currentStep = 4
	case "layout":
		currentStep = 5
	case "pane_command":
		currentStep = 5 + builder.currentPane*2 + 1
	case "pane_title":
		currentStep = 5 + builder.currentPane*2 + 2
	}

	return "Creating template: " + builder.name + " | Step " + string(rune('0'+currentStep)) + "/" + string(rune('0'+totalSteps))
}

// renderMainContent renders the main content area
func (m model) renderMainContent() string {
	contentWidth, contentHeight := m.calculateLayout()

	// Implement your main content rendering here
	// Example:
	// return m.renderItemList(contentWidth, contentHeight)

	placeholder := "Main content area\n\n"
	placeholder += "Implement your content rendering in renderMainContent()\n\n"
	placeholder += "Press ? for help\n"
	placeholder += "Press q to quit"

	return contentStyle.Width(contentWidth).Height(contentHeight).Render(placeholder)
}

// renderLeftPane renders the left pane in dual-pane mode
func (m model) renderLeftPane(width int) string {
	_, contentHeight := m.calculateLayout()

	// Implement left pane content
	content := "Left Pane\n\n"
	content += "Width: " + string(rune(width))

	return leftPaneStyle.Width(width).Height(contentHeight).Render(content)
}

// renderRightPane renders the right pane in dual-pane mode
func (m model) renderRightPane(width int) string {
	_, contentHeight := m.calculateLayout()

	// Implement right pane content
	content := "Right Pane (Preview)\n\n"
	content += "Width: " + string(rune(width))

	return rightPaneStyle.Width(width).Height(contentHeight).Render(content)
}

// renderDivider renders the vertical divider between panes
func (m model) renderDivider() string {
	_, contentHeight := m.calculateLayout()
	divider := strings.Repeat("│\n", contentHeight)
	return dividerStyle.Render(divider)
}

// Error and minimal views

// renderErrorView renders an error message
func (m model) renderErrorView() string {
	content := "Error: " + m.err.Error() + "\n\n"
	content += "Press q to quit"
	return errorStyle.Render(content)
}

// renderMinimalView renders a minimal view for small terminals
func (m model) renderMinimalView() string {
	content := "Terminal too small\n"
	content += "Minimum: 30x15\n"
	content += "Press q to quit"
	return errorStyle.Render(content)
}

// renderUnifiedView renders the unified 3-panel adaptive layout
// Layout: Sessions (top, 40-50%) | Preview (middle, 40-30%) | Command (bottom, 20% fixed)
// In watcher mode: Sessions panel uses full height (no preview/command)
func (m model) renderUnifiedView() string {
	var sections []string

	// Title bar (hide at compact/minimal widths to reclaim a row)
	if m.config.UI.ShowTitle && m.widthTier() == "full" {
		sections = append(sections, m.renderTitleBar())
	}

	// Calculate available content height
	contentWidth, contentHeight := m.calculateLayout()

	// Add back the 2 lines that calculateLayout() subtracted for borders
	// calculateAdaptivePanelHeights() will handle all 3 panels' borders (6 lines total)
	contentHeight += 2

	// Watcher mode: sessions panel uses full height
	if m.watcherMode {
		// Full height for sessions panel (only subtract 2 for its own borders)
		sessionsHeight := contentHeight

		var topPanelContent []string
		var topPanelName string
		if m.sessionsTab == "templates" {
			topPanelContent = m.templatesContent
			topPanelName = "templates"
		} else {
			topPanelContent = m.sessionsContent
			topPanelName = "sessions"
		}
		sessionsPanel := m.renderDynamicPanel(topPanelName, contentWidth, sessionsHeight, topPanelContent)
		sections = append(sections, sessionsPanel)

		// Status bar
		if m.config.UI.ShowStatus {
			sections = append(sections, m.renderStatusBar())
		}

		return lipgloss.JoinVertical(lipgloss.Left, sections...)
	}

	// Normal mode: 3-panel layout (or 2-panel when maximized)
	// Get adaptive panel heights based on focus state
	sessionsHeight, previewHeight, commandHeight := m.calculateAdaptivePanelHeights(contentHeight)

	// Render each panel with appropriate content (top panel switches between sessions/templates)
	var topPanelContent []string
	var topPanelName string
	if m.sessionsTab == "templates" {
		topPanelContent = m.templatesContent
		topPanelName = "templates"
	} else {
		topPanelContent = m.sessionsContent
		topPanelName = "sessions"
	}
	sessionsPanel := m.renderDynamicPanel(topPanelName, contentWidth, sessionsHeight, topPanelContent)
	commandPanel := m.renderDynamicPanel("command", contentWidth, commandHeight, m.commandContent)

	// Stack panels vertically (skip preview when maximized)
	if m.sessionsMaximized {
		// 2-panel layout: sessions + command (no preview)
		sections = append(sections, sessionsPanel, commandPanel)
	} else {
		// 3-panel layout: sessions + preview + command
		previewPanel := m.renderDynamicPanel("preview", contentWidth, previewHeight, m.previewContent)
		sections = append(sections, sessionsPanel, previewPanel, commandPanel)
	}

	// Status bar
	if m.config.UI.ShowStatus {
		sections = append(sections, m.renderStatusBar())
	}

	return lipgloss.JoinVertical(lipgloss.Left, sections...)
}

// renderDynamicPanel renders a single dynamic panel with border and content
func (m model) renderDynamicPanel(panelName string, width, height int, content []string) string {
	// In unified layout, panels are focused based on focusState
	isFocused := false
	switch m.focusState {
	case FocusSessions:
		isFocused = (panelName == "sessions" || panelName == "templates")
	case FocusPreview:
		isFocused = (panelName == "preview")
	case FocusCommand:
		isFocused = (panelName == "command")
	}

	// Create border style based on focus
	borderColor := lipgloss.Color("240") // Dim gray

	if isFocused {
		borderColor = colorPrimary // Bright blue
	}

	// Panel titles
	titles := map[string]string{
		"sessions":  "Sessions",
		"templates": "Templates",
		"preview":   "Preview",
		"command":   "Command",
	}

	// Responsive panel titles based on width tier
	tier := m.widthTier()

	// Compact/minimal title labels
	compactTitles := map[string]string{
		"sessions":  "Sess",
		"templates": "Tmpl",
		"preview":   "Prev",
		"command":   "Cmd",
	}
	minimalTitles := map[string]string{
		"sessions":  "S",
		"templates": "T",
		"preview":   "P",
		"command":   "C",
	}

	var title string
	if isFocused {
		// Special rendering for Sessions/Templates tabs (top panel)
		if panelName == "sessions" || panelName == "templates" {
			activeTabStyle := lipgloss.NewStyle().Foreground(colorPrimary).Bold(true)
			inactiveTabStyle := lipgloss.NewStyle().Foreground(colorForeground)

			var sessLabel, tmplLabel string
			switch tier {
			case "minimal":
				sessLabel = "S"
				tmplLabel = "T"
			case "compact":
				sessLabel = "Sess"
				tmplLabel = "Tmpl"
			default:
				sessLabel = "Sessions"
				tmplLabel = "Templates"
			}

			if panelName == "sessions" {
				sessLabel = activeTabStyle.Render(sessLabel)
				tmplLabel = inactiveTabStyle.Render(tmplLabel)
			} else {
				sessLabel = inactiveTabStyle.Render(sessLabel)
				tmplLabel = activeTabStyle.Render(tmplLabel)
			}

			title = " " + sessLabel + "|" + tmplLabel + " ● "
		} else {
			// Other panels: simple focused indicator
			switch tier {
			case "minimal":
				title = " " + minimalTitles[panelName] + " ● "
			case "compact":
				title = " " + compactTitles[panelName] + " ● "
			default:
				title = " " + titles[panelName] + " ● "
			}
		}
	} else {
		// Unfocused: plain title
		if panelName == "sessions" || panelName == "templates" {
			switch tier {
			case "minimal":
				title = " S|T "
			case "compact":
				title = " Sess|Tmpl "
			default:
				title = " Sessions | Templates "
			}
		} else {
			switch tier {
			case "minimal":
				title = " " + minimalTitles[panelName] + " "
			case "compact":
				title = " " + compactTitles[panelName] + " "
			default:
				title = " " + titles[panelName] + " "
			}
		}
	}

	// Calculate max text width
	maxTextWidth := width - 2 // -2 for borders
	if maxTextWidth < 1 {
		maxTextWidth = 1
	}

	// Calculate exact content area height
	// Since title is now in border, we get full inner height for content
	innerHeight := height - 2 // Remove borders

	// Reserve 1 line for contextual help when focused (skip for sessions/templates to maximize list space)
	helpLine := ""
	if isFocused && panelName != "sessions" && panelName != "templates" {
		helpLine = m.getContextualPanelHelp(panelName)
	}

	availableContentLines := innerHeight
	if helpLine != "" {
		availableContentLines-- // Reserve space for help line
	}

	if availableContentLines < 1 {
		availableContentLines = 1
	}

	// Determine scroll offset for sessions/templates panels
	scrollOffset := 0
	if panelName == "sessions" || panelName == "templates" {
		scrollOffset = m.sessionsScrollOffset
	}

	// Build content lines (truncate if too long to prevent wrapping)
	var lines []string
	startIdx := scrollOffset
	for i := 0; i < availableContentLines && (startIdx + i) < len(content); i++ {
		line := content[startIdx + i]

		// Apply styling based on tags
		if line == "DIVIDER" {
			// Full-width divider
			line = strings.Repeat("─", maxTextWidth)
		} else if line == "SESSION_DIVIDER" {
			// Session divider with indent
			dividerWidth := maxTextWidth - 2
			if dividerWidth < 1 {
				dividerWidth = 1
			}
			line = "  " + strings.Repeat("┄", dividerWidth)
		} else if strings.HasPrefix(line, "DETAILS:header:") {
			// Section header style
			text := strings.TrimPrefix(line, "DETAILS:header:")
			line = sectionHeaderStyle.Render(truncateString(text, maxTextWidth))
		} else if strings.HasPrefix(line, "DETAILS:detail:") {
			// Detail text style (dimmed)
			text := strings.TrimPrefix(line, "DETAILS:detail:")
			line = dimmedStyle.Render(truncateString(text, maxTextWidth))
		} else if strings.HasPrefix(line, "HEADER:") {
			// Table header style (bold + primary color)
			text := strings.TrimPrefix(line, "HEADER:")
			line = tableHeaderStyle.Render(truncateString(text, maxTextWidth))
		} else if strings.HasPrefix(line, "CURRENT:") {
			// Current session style (cyan text, bold) - takes precedence over Claude
			text := strings.TrimPrefix(line, "CURRENT:")
			line = currentSessionStyle.Render(truncateString(text, maxTextWidth))
		} else if strings.HasPrefix(line, "CLAUDE:") {
			// Claude session style (orange text)
			text := strings.TrimPrefix(line, "CLAUDE:")
			line = claudeSessionStyle.Render(truncateString(text, maxTextWidth))
		} else if strings.HasPrefix(line, "SELECTED:") {
			// Selected tree item style (bold + underline)
			text := strings.TrimPrefix(line, "SELECTED:")
			// If text already contains ANSI escape codes (pre-styled table view), pass through as-is
			if strings.Contains(text, "\033[") {
				line = text
			} else {
				line = selectedTreeItemStyle.Render(truncateString(text, maxTextWidth))
			}
		} else {
			// Normal text
			line = truncateString(line, maxTextWidth)
		}

		lines = append(lines, line)
	}

	// Compute scroll info for sessions/templates panels (rendered in bottom border)
	bottomBorderInfo := ""
	if panelName == "sessions" || panelName == "templates" {
		totalLines := len(content)
		canScrollUp := scrollOffset > 0
		canScrollDown := (startIdx + availableContentLines) < totalLines

		if canScrollUp || canScrollDown {
			bottomBorderInfo = fmt.Sprintf(" %d-%d of %d ",
				scrollOffset+1,
				min(scrollOffset+availableContentLines, totalLines),
				totalLines)
		}
	}

	// Fill remaining space to ensure consistent height (minus 1 for help line if present)
	targetLines := innerHeight
	if helpLine != "" {
		targetLines = innerHeight - 1
	}
	for len(lines) < targetLines {
		lines = append(lines, "")
	}

	// Add contextual help line at the bottom when focused
	if helpLine != "" {
		helpStyle := lipgloss.NewStyle().Foreground(colorDimmed).Italic(true)
		lines = append(lines, helpStyle.Render(truncateString(helpLine, maxTextWidth)))
	}

	contentStr := strings.Join(lines, "\n")

	// Create custom border with title in top border (lazygit style)
	border := lipgloss.RoundedBorder()

	// Calculate how much space we have for the title in the top border
	// width - 2 for corner characters
	topBorderSpace := width - 2

	// Create title with padding
	titleLen := lipgloss.Width(title)
	if titleLen > topBorderSpace - 2 {
		// Truncate title if too long
		title = truncateString(title, topBorderSpace - 2)
		titleLen = lipgloss.Width(title)
	}

	// Build top border: ╭ title ─────╮
	// Style border characters to maintain color
	borderStyle := lipgloss.NewStyle().Foreground(borderColor)

	leftBorder := borderStyle.Render(border.TopLeft)
	rightBorder := borderStyle.Render(border.TopRight)
	fillChar := border.Top

	// Calculate fill needed after title
	fillNeeded := topBorderSpace - titleLen
	if fillNeeded < 0 {
		fillNeeded = 0
	}

	// Build top border with styled elements
	fillString := borderStyle.Render(strings.Repeat(fillChar, fillNeeded))
	customTopBorder := leftBorder + title + fillString + rightBorder

	// Build the complete box manually to ensure proper border connection
	var boxLines []string

	// Add top border
	boxLines = append(boxLines, customTopBorder)

	// Add content lines with left/right borders (reuse borderStyle from above)
	contentLines := strings.Split(contentStr, "\n")
	for _, line := range contentLines {
		// Safety: ensure line is never longer than maxTextWidth (re-truncate if needed)
		lineWidth := lipgloss.Width(line)
		if lineWidth > maxTextWidth {
			line = truncateString(line, maxTextWidth)
			lineWidth = lipgloss.Width(line)
		}
		// Ensure line is exactly maxTextWidth (pad if needed)
		if lineWidth < maxTextWidth {
			line = line + strings.Repeat(" ", maxTextWidth-lineWidth)
		}
		// Style the border characters to prevent color bleeding from styled content
		leftBorder := borderStyle.Render(border.Left)
		rightBorder := borderStyle.Render(border.Right)
		boxLines = append(boxLines, leftBorder+line+rightBorder)
	}

	// Add bottom border with optional scroll info embedded (e.g., ╰── 4-16 of 20 ──╯)
	bottomLeft := borderStyle.Render(border.BottomLeft)
	bottomRight := borderStyle.Render(border.BottomRight)
	var bottomBorder string
	if bottomBorderInfo != "" {
		infoLen := lipgloss.Width(bottomBorderInfo)
		remainingFill := maxTextWidth - infoLen
		if remainingFill < 2 {
			// Not enough room for info, just fill
			bottomBorder = bottomLeft + borderStyle.Render(strings.Repeat(border.Bottom, maxTextWidth)) + bottomRight
		} else {
			leftFill := remainingFill / 2
			rightFill := remainingFill - leftFill
			infoStyle := lipgloss.NewStyle().Foreground(colorDimmed).Italic(true)
			bottomBorder = bottomLeft +
				borderStyle.Render(strings.Repeat(border.Bottom, leftFill)) +
				infoStyle.Render(bottomBorderInfo) +
				borderStyle.Render(strings.Repeat(border.Bottom, rightFill)) +
				bottomRight
		}
	} else {
		bottomBorder = bottomLeft + borderStyle.Render(strings.Repeat(border.Bottom, maxTextWidth)) + bottomRight
	}
	boxLines = append(boxLines, bottomBorder)

	// Join all lines and apply color
	fullBox := strings.Join(boxLines, "\n")

	return lipgloss.NewStyle().
		Foreground(borderColor).
		Render(fullBox)
}

// renderVerticalDivider renders a vertical divider between panels
func renderVerticalDivider(height int) string {
	dividerStyle := lipgloss.NewStyle().
		Foreground(lipgloss.Color("240"))

	var lines []string
	for i := 0; i < height; i++ {
		lines = append(lines, "│")
	}

	return dividerStyle.Render(strings.Join(lines, "\n"))
}

// Helper functions

// truncateString truncates a string to fit within maxWidth
func truncateString(s string, maxWidth int) string {
	// Use lipgloss.Width to properly measure visual width (ignoring ANSI codes)
	currentWidth := lipgloss.Width(s)
	if currentWidth <= maxWidth {
		return s
	}
	if maxWidth <= 3 {
		// Very narrow, just show first few runes
		runes := []rune(s)
		if len(runes) > maxWidth {
			return string(runes[:maxWidth])
		}
		return s
	}

	// Truncate by removing runes from the end until we fit
	runes := []rune(s)
	targetWidth := maxWidth - 3 // Reserve space for "..."

	for len(runes) > 0 && lipgloss.Width(string(runes)) > targetWidth {
		runes = runes[:len(runes)-1]
	}

	return string(runes) + "..."
}

// padRight pads a string with spaces to reach the desired width
func padRight(s string, width int) string {
	currentWidth := lipgloss.Width(s)
	if currentWidth >= width {
		return s
	}
	return s + strings.Repeat(" ", width-currentWidth)
}

// centerString centers a string within the given width
func centerString(s string, width int) string {
	strWidth := lipgloss.Width(s)
	if strWidth >= width {
		return s
	}
	leftPad := (width - strWidth) / 2
	rightPad := width - strWidth - leftPad
	return strings.Repeat(" ", leftPad) + s + strings.Repeat(" ", rightPad)
}

// renderScrollingFooter renders footer text with horizontal scrolling if enabled
// If text fits within width, returns as-is. If scrolling is enabled and text is too long,
// creates a looping marquee effect. Otherwise truncates with "..."
func (m model) renderScrollingFooter(text string, availableWidth int) string {
	textLen := visualWidth(text)

	// If text fits, no modification needed
	if textLen <= availableWidth {
		return text
	}

	// If scrolling is active, create looping marquee
	if m.footerScrolling {
		// Add visual indicator and separator for smooth loop
		indicator := "⏵ " // Indicates scrolling is active
		paddedText := indicator + text + "   •   " + indicator + text

		// Convert to runes to handle multi-byte unicode characters (↑, ↓, •, etc.)
		runes := []rune(paddedText)
		runeCount := len(runes)

		// Calculate scroll position with wrapping
		scrollPos := m.footerOffset % runeCount

		// Extract visible portion (by rune, not byte)
		var result strings.Builder
		for i := 0; i < availableWidth && i < runeCount; i++ {
			charPos := (scrollPos + i) % runeCount
			result.WriteRune(runes[charPos])
		}

		return result.String()
	}

	// Not scrolling - truncate with "..."
	return truncateString(text, availableWidth)
}
