// AgentMode.h — persistent Conductor / Claude / Codex task dashboard.
//
// The Mac bridge pushes a privacy-minimized snapshot to POST /api/agents.
// Only the newest four rows are kept because that is all the 240x240 display
// can show legibly. Prompts, responses and credentials never reach the device.
#pragma once

#include "Mode.h"
#include "config.h"

enum AgentState : uint8_t {
  AGENT_IDLE = 0,
  AGENT_WORKING,
  AGENT_NEEDS_INPUT,
  AGENT_DONE,
  AGENT_FAILED,
};

struct AgentRow {
  char       label[AGENT_LABEL_LEN];
  char       tool[AGENT_TOOL_LEN];
  AgentState state;
};

class AgentMode : public DisplayMode {
 public:
  const char* id() const override { return "agents"; }
  uint8_t     modeConst() const override { return MODE_AGENTS; }

  void begin(const Settings& s) override;
  void service(const Settings& s) override;
  void invalidate(const Settings& s) override;
  void wake(const Settings& s) override;

  bool    apply(const String& body);
  uint8_t count() const { return count_; }
  uint8_t countState(AgentState state) const;
  uint32_t updatedAgoSec() const;

 private:
  void render();

  AgentRow rows_[AGENT_MAX_ROWS] = {};
  uint8_t  count_ = 0;
  uint32_t updatedMs_ = 0;
  uint32_t lastAgeRenderMs_ = 0;
  bool     dirty_ = true;
};

extern AgentMode g_agentMode;
