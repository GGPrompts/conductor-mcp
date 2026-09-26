package main

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// layoutTestModel builds a model with fixed content and no tmux access, sized
// directly (setSize would refresh content from tmux).
func layoutTestModel(width, height int) model {
	long := strings.Repeat("x", 400)
	return model{
		config:          getDefaultConfig(),
		width:           width,
		height:          height,
		focusState:      FocusSessions,
		sessionsTab:     "sessions",
		sessionsContent: []string{"session-a", long},
		previewContent:  []string{"pane line", long},
		commandContent:  []string{"> _"},
	}
}

// TestLayoutFitsWindow renders both layouts and checks the frame never
// overflows the window and that the list and preview share a row only when
// the width reaches sideBySideMinWidth (cm-j39).
func TestLayoutFitsWindow(t *testing.T) {
	cases := []struct {
		width, height int
		sideBySide    bool
	}{
		{100, 40, false},
		{sideBySideMinWidth - 1, 40, false},
		{sideBySideMinWidth, 40, true},
		{180, 50, true},
	}
	for _, c := range cases {
		m := layoutTestModel(c.width, c.height)
		if got := m.isSideBySide(); got != c.sideBySide {
			t.Fatalf("%dx%d: isSideBySide = %v, want %v", c.width, c.height, got, c.sideBySide)
		}
		lines := strings.Split(m.View(), "\n")
		if len(lines) != c.height {
			t.Errorf("%dx%d: rendered %d lines, want %d", c.width, c.height, len(lines), c.height)
		}
		shared := false
		// The 2-line status bar is width+2 wide (statusStyle padding) and
		// JoinVertical pads every row to it; both predate this layout, so
		// check the panel rows with that trailing pad trimmed.
		for i, line := range lines[:len(lines)-2] {
			if w := lipgloss.Width(strings.TrimRight(line, " ")); w > c.width {
				t.Errorf("%dx%d: line %d is %d wide", c.width, c.height, i, w)
			}
			if strings.Contains(line, "Sessions") && strings.Contains(line, "Preview") {
				shared = true
			}
		}
		if shared != c.sideBySide {
			t.Errorf("%dx%d: list and preview on one row = %v, want %v", c.width, c.height, shared, c.sideBySide)
		}
	}
}

// TestSideBySideMouseFocus checks that a click in the right column of the
// side by side row focuses the preview and one in the left column the list.
func TestSideBySideMouseFocus(t *testing.T) {
	m := layoutTestModel(160, 40)
	listWidth, _ := m.sideBySideWidths()
	click := func(x, y int) int {
		next, _ := m.handleUnifiedPanelClick(tea.MouseMsg{X: x, Y: y, Type: tea.MouseLeft})
		return next.(model).focusState
	}
	if got := click(listWidth+5, 10); got != FocusPreview {
		t.Errorf("right column click: focus = %v, want preview", got)
	}
	if got := click(5, 10); got != FocusSessions {
		t.Errorf("left column click: focus = %v, want sessions", got)
	}
	if got := click(5, 40-3); got != FocusCommand {
		t.Errorf("command row click: focus = %v, want command", got)
	}
}
