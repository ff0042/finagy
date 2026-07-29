# FinAlly: AI Portfolio Strategist & Trading Workstation

## 1. Project Vision & Architecture
FinAlly is a unified trading workstation featuring a React frontend and a FastAPI Python backend. Its core capability is an embedded, context-aware LLM (FinAlly) that acts as a proactive Portfolio Strategist. 

The AI is capable of:
- **Interactive Assistance:** Answering financial queries and generating trade orders via the chat interface.
- **Background Autonomy:** Waking up on a cron schedule (`apscheduler`) to evaluate the portfolio without user intervention.
- **Context-Aware Communication:** Outputting trade blueprints directly in the chat when the user is at the keyboard, but routing alerts via SMS (Twilio Webhooks) when operating in the background.

## 2. Completed Milestones (Current Capabilities)
- **Schwab API Integration:** Core trading logic is wired up.
- **Mock Fallbacks:** If Schwab API is disconnected, the system seamlessly falls back to a deterministic mocked LLM and a Geometric Brownian Motion (GBM) market data simulator.
- **Autonomy Toggle:** A UI switch (Co-Pilot vs. Auto-Pilot) that dynamically rewrites the AI's system prompt.
  - *Co-Pilot:* AI formulates recommendations and explicitly waits for user approval before outputting JSON orders.
  - *Auto-Pilot:* AI acts as the primary execution engine, firing JSON orders immediately.
- **Enterprise Twilio Webhook Security:** The `/api/twilio/webhook` endpoint is secured with strict cryptographic signature validation (`RequestValidator`) to prevent HTTP spoofing, guaranteeing texts only originate from the configured `USER_PHONE_NUMBER`.

## 3. Methodical Test Plan (Current Phase)
To verify the complex logic built in this sprint without risking real capital, follow this mock testing procedure:

1. **Prerequisites:** 
   - Ensure the `.env` file has a placeholder `TWILIO_AUTH_TOKEN="your_twilio_auth_token_here"` so the cryptographic check is bypassed for local mock testing.
   - Run the Python backend locally (`python main.py`).
2. **Test 1: Interactive Advice (Co-Pilot)**
   - Set toggle to "Co-Pilot".
   - *Prompt:* "Please construct a portfolio that maximizes Sharpe ratio across 4 sectors for $25k."
   - *Expected:* AI responds in the chat with a plan, but DOES NOT output JSON trade orders. It asks for your permission to proceed.
3. **Test 2: Interactive Execution (Auto-Pilot)**
   - Set toggle to "Auto-Pilot".
   - *Prompt:* "Execute the portfolio plan."
   - *Expected:* AI immediately outputs the JSON `"orders"` array to execute the trades.
4. **Test 3: Background Wakeup & SMS Logic**
   - *Prompt:* "Schedule a background evaluation to run every minute (* * * * *)."
   - *Expected:* The AI calls the `schedule_evaluation` tool. Wait one minute. Check the Python backend console—you should see `[BACKGROUND JOB TRIGGERED]` followed by an SMS message being "sent" (printed to console).
   - Refresh the frontend browser. The background SMS conversation should now be visible in your chat history!

## 4. Future Phases (The Backlog)

### Phase 1: Twilio Go-Live
- Create Twilio Account and get a temporary number.
- Update `TWILIO_AUTH_TOKEN` in `.env` to activate cryptographic security.
- Configure Twilio SMS Webhook to point to the backend (via `ngrok` for local testing).
- Create a TwiML Bin (`<Response><Reject/></Response>`) to silently drop incoming voice calls for free.
- Port the legacy Ooma number over.

### Phase 2: Cloud Deployment
- Spin up an AWS EC2 or Lightsail instance under the existing AWS domain.
- Deploy the FastAPI backend to run 24/7 (eliminating the need for `ngrok`).
- Configure Nginx as a reverse proxy to route traffic for FinAlly and Sarah's website on the same machine to consolidate costs.

### Phase 3: Real Trading
- Remove the `LLM_MOCK` overrides.
- Connect the production Schwab API credentials.
- Fund the account and allow FinAlly to begin executing real JSON trade orders.

### Phase 4: Voice AI Broker (Moonshot)
- Upgrade the Twilio integration to support real-time Media Streams (WebSockets).
- Connect an audio-native LLM (OpenAI Realtime / Deepgram) to allow the user to literally call the Ooma number and speak to FinAlly over the phone to get real-time market updates and execute trades via voice.
