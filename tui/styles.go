package main

import (
	"github.com/charmbracelet/lipgloss"
)

// styles.go - Visual Styling
// Purpose: All Lipgloss style definitions
// When to extend: Add new styles when introducing new visual components

// Color palette - Dark theme (default)
var (
	colorPrimary    = lipgloss.Color("#61AFEF") // Blue
	colorSecondary  = lipgloss.Color("#C678DD") // Purple
	colorBackground = lipgloss.Color("#282C34") // Dark gray
	colorForeground = lipgloss.Color("#ABB2BF") // Light gray
	colorAccent     = lipgloss.Color("#98C379") // Green
	colorError      = lipgloss.Color("#E06C75") // Red
	colorWarning    = lipgloss.Color("#E5C07B") // Yellow
	colorInfo       = lipgloss.Color("#56B6C2") // Cyan
	colorOrange     = lipgloss.Color("#D19A66") // Orange (for Claude sessions)

	// Semantic colors
	colorSelected = lipgloss.Color("#61AFEF")
	colorFocused  = lipgloss.Color("#98C379")
	colorDimmed   = lipgloss.Color("#5C6370")
	colorBorder   = lipgloss.Color("#3E4451")
)

// Base styles

var baseStyle = lipgloss.NewStyle().
	Foreground(colorForeground)

// Layout styles

var titleStyle = lipgloss.NewStyle().
	Foreground(colorPrimary).
	Bold(true).
	Padding(0, 1)

var statusStyle = lipgloss.NewStyle().
	Foreground(colorDimmed).
	Padding(0, 1)

var contentStyle = lipgloss.NewStyle().
	Padding(0, 1)

var leftPaneStyle = lipgloss.NewStyle().
	BorderStyle(lipgloss.NormalBorder()).
	BorderForeground(colorBorder).
	BorderLeft(false).
	BorderTop(false).
	BorderBottom(false).
	Padding(0, 1)

var rightPaneStyle = lipgloss.NewStyle().
	BorderStyle(lipgloss.NormalBorder()).
	BorderForeground(colorBorder).
	BorderRight(false).
	BorderTop(false).
	BorderBottom(false).
	Padding(0, 1)

var dividerStyle = lipgloss.NewStyle().
	Foreground(colorBorder)

// Component styles

var selectedStyle = lipgloss.NewStyle().
	Foreground(colorSelected).
	Bold(true).
	Background(lipgloss.Color("#3E4451"))

var focusedStyle = lipgloss.NewStyle().
	Foreground(colorFocused).
	Bold(true)

var dimmedStyle = lipgloss.NewStyle().
	Foreground(colorDimmed)

var highlightStyle = lipgloss.NewStyle().
	Foreground(colorAccent).
	Bold(true)

var sectionHeaderStyle = lipgloss.NewStyle().
	Foreground(colorSecondary).
	Bold(true)

var claudeSessionStyle = lipgloss.NewStyle().
	Foreground(colorOrange).
	Bold(true)

var currentSessionStyle = lipgloss.NewStyle().
	Foreground(colorInfo). // Cyan - stands out for "this is where you are"
	Bold(true)

var selectedTreeItemStyle = lipgloss.NewStyle().
	Foreground(colorPrimary).
	Bold(true).
	Reverse(true) // Inverse video for high visibility

// List styles

var listItemStyle = lipgloss.NewStyle().
	Foreground(colorForeground)

var listSelectedStyle = lipgloss.NewStyle().
	Foreground(colorSelected).
	Bold(true).
	Background(lipgloss.Color("#3E4451")).
	Padding(0, 1)

var listCursorStyle = lipgloss.NewStyle().
	Foreground(colorAccent).
	Bold(true)

// Button styles

var buttonStyle = lipgloss.NewStyle().
	Foreground(colorForeground).
	Background(colorBorder).
	Padding(0, 2).
	MarginRight(1)

var buttonActiveStyle = lipgloss.NewStyle().
	Foreground(lipgloss.Color("#282C34")).
	Background(colorPrimary).
	Padding(0, 2).
	MarginRight(1).
	Bold(true)

// Tab styles (for 3-tab layout)

var activeTabStyle = lipgloss.NewStyle().
	Foreground(colorPrimary).
	Background(lipgloss.Color("#282C34")).
	Bold(true)

var inactiveTabStyle = lipgloss.NewStyle().
	Foreground(lipgloss.Color("240"))

// Dialog styles

var dialogBoxStyle = lipgloss.NewStyle().
	Border(lipgloss.RoundedBorder()).
	BorderForeground(colorPrimary).
	Padding(1, 2).
	Width(50)

var dialogTitleStyle = lipgloss.NewStyle().
	Foreground(colorPrimary).
	Bold(true).
	Align(lipgloss.Center)

var dialogContentStyle = lipgloss.NewStyle().
	Foreground(colorForeground).
	MarginTop(1).
	MarginBottom(1)

// Input styles

var inputStyle = lipgloss.NewStyle().
	Foreground(colorForeground).
	Background(colorBorder).
	Padding(0, 1)

var inputFocusedStyle = lipgloss.NewStyle().
	Foreground(colorForeground).
	Background(colorBorder).
	BorderStyle(lipgloss.NormalBorder()).
	BorderForeground(colorPrimary).
	Padding(0, 1)

// Message styles

var errorStyle = lipgloss.NewStyle().
	Foreground(colorError).
	Bold(true).
	Padding(1, 2)

var warningStyle = lipgloss.NewStyle().
	Foreground(colorWarning).
	Bold(true).
	Padding(1, 2)

var infoStyle = lipgloss.NewStyle().
	Foreground(colorInfo).
	Padding(1, 2)

var successStyle = lipgloss.NewStyle().
	Foreground(colorAccent).
	Bold(true).
	Padding(1, 2)

// Table styles

var tableHeaderStyle = lipgloss.NewStyle().
	Foreground(colorPrimary).
	Bold(true).
	BorderStyle(lipgloss.NormalBorder()).
	BorderBottom(true).
	BorderForeground(colorBorder)

var tableCellStyle = lipgloss.NewStyle().
	Foreground(colorForeground).
	Padding(0, 1)

var tableSelectedStyle = lipgloss.NewStyle().
	Foreground(colorSelected).
	Bold(true).
	Background(lipgloss.Color("#3E4451"))

// Menu styles

var menuItemStyle = lipgloss.NewStyle().
	Foreground(colorForeground).
	Padding(0, 2)

var menuSelectedStyle = lipgloss.NewStyle().
	Foreground(colorBackground).
	Background(colorPrimary).
	Bold(true).
	Padding(0, 2)

var menuSeparatorStyle = lipgloss.NewStyle().
	Foreground(colorBorder)

// Helper functions for dynamic styling

// applyTheme applies a theme to all styles
func applyTheme(theme ThemeColors) {
	colorPrimary = lipgloss.Color(theme.Primary)
	colorSecondary = lipgloss.Color(theme.Secondary)
	colorBackground = lipgloss.Color(theme.Background)
	colorForeground = lipgloss.Color(theme.Foreground)
	colorAccent = lipgloss.Color(theme.Accent)
	colorError = lipgloss.Color(theme.Error)

	// Update all styles
	titleStyle = titleStyle.Foreground(colorPrimary)
	statusStyle = statusStyle.Foreground(colorDimmed)
	selectedStyle = selectedStyle.Foreground(colorPrimary)
	// ... update other styles as needed
}

// getTheme returns the current theme colors
func getTheme() ThemeColors {
	return ThemeColors{
		Primary:    string(colorPrimary),
		Secondary:  string(colorSecondary),
		Background: string(colorBackground),
		Foreground: string(colorForeground),
		Accent:     string(colorAccent),
		Error:      string(colorError),
	}
}
