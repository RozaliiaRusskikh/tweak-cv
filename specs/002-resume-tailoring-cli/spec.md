# Feature Specification: AI Resume Tailoring CLI

**Feature Branch**: `002-resume-tailoring-cli`

**Created**: 2026-05-28

**Status**: Draft

**Input**: User description: "A single-user CLI tool that takes a job description as input, extracts key skills and keywords, then uses AI to tailor the user's base resume by reordering bullets, adjusting the summary, and matching terminology. The tailored resume is scored automatically for keyword coverage and hallucination before being sent as a Slack message with Approve, Edit, and Reject buttons. Approve exports a PDF saved locally. Edit opens a conversation in the Slack thread where the user describes changes, the AI applies them, and the loop repeats (capped at 3 iterations). Reject discards the result. Unanswered messages expire after 24 hours. All scores and user decisions are logged for observability."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tailor Resume and Send for Review (Priority: P1)

A job seeker has a base resume stored locally and finds a job posting they want to apply for. They run the tool from their terminal, provide the job description, and the system produces a tailored resume—adapted to match the job's required skills and language—then posts it to their Slack workspace for review. The Slack message shows keyword coverage and hallucination scores alongside three buttons: Approve, Edit, Reject.

**Why this priority**: This is the core value delivery of the entire tool. Everything else depends on this working first.

**Independent Test**: Can be fully tested by running the CLI with a sample job description and verifying a Slack message appears with the tailored resume, scores, and action buttons.

**Acceptance Scenarios**:

1. **Given** the user has a configured base resume and provides a job description text, **When** they run the tool, **Then** a tailored resume is generated and a Slack message is sent within 2 minutes containing the resume, keyword coverage score, hallucination score, and Approve/Edit/Reject buttons.
2. **Given** the user provides a job description as a file path, **When** they run the tool, **Then** the tool reads the file and proceeds identically to direct text input.
3. **Given** the job description contains no identifiable skills or keywords, **When** the tool processes it, **Then** the user receives an error message before a Slack message is sent, explaining the job description is insufficient.
4. **Given** the base resume file is missing or cannot be read, **When** the user runs the tool, **Then** the tool exits with a clear error message before sending anything to Slack.

---

### User Story 2 - Approve and Export as PDF (Priority: P2)

After reviewing the tailored resume in Slack, the job seeker is satisfied with the result and clicks Approve. The system exports the tailored resume as a PDF file saved to a local directory on their machine.

**Why this priority**: Approval with PDF export is the successful completion of the primary workflow. Without it, the tool delivers no tangible output.

**Independent Test**: Can be fully tested by clicking Approve on a Slack message and confirming a valid PDF file appears in the configured output directory.

**Acceptance Scenarios**:

1. **Given** the user clicks Approve on the Slack message, **Then** a PDF of the tailored resume is saved to the configured output directory, and Slack confirms the export with the file path.
2. **Given** the PDF output directory does not exist or is not writable, **When** Approve is clicked, **Then** the user receives an error in Slack with the specific problem, and the tailored resume content is preserved so the user can retry.
3. **Given** the user approves a resume from the 3rd edit iteration, **Then** the PDF reflects the most recent edited version.

---

### User Story 3 - Request Edits via Slack Thread (Priority: P3)

The job seeker reviews the tailored resume in Slack but wants specific changes—perhaps a bullet doesn't accurately represent their experience, or the summary tone is off. They click Edit, describe the changes in plain language in the Slack thread, and receive an updated tailored resume in the same thread. This loop can repeat up to 3 times.

**Why this priority**: Editing is the refinement layer that increases output quality. It is valuable but the tool still delivers without it.

**Independent Test**: Can be fully tested by clicking Edit, typing a change request in the thread, and confirming an updated resume appears in the same thread with revised scores and action buttons.

**Acceptance Scenarios**:

1. **Given** the user clicks Edit, **When** they type a change request in the Slack thread, **Then** an updated tailored resume is posted in the same thread within 90 seconds, along with updated scores and action buttons.
2. **Given** the user has completed 3 edit iterations, **When** the 3rd updated resume is posted, **Then** only Approve and Reject buttons are shown—no Edit button.
3. **Given** the user attempts to send a second edit request in the thread before receiving a response, **Then** the system acknowledges only the first request and informs the user to wait for the updated resume.
4. **Given** the user's edit request is ambiguous, **Then** the system applies its best interpretation and notes what it changed in the thread reply.

---

### User Story 4 - Reject Result or Let It Expire (Priority: P4)

The job seeker reviews the tailored resume and decides it is not suitable for the role—or they simply forget to respond. Clicking Reject discards the result with no further action. If no response is given within 24 hours, the system expires the message automatically.

**Why this priority**: Graceful exit paths (Reject and expiry) are necessary for a complete and safe workflow, but represent the unhappy path.

**Independent Test**: Can be fully tested by clicking Reject and confirming no PDF is created and the log records a "Rejected" outcome; and by waiting 24 hours (or simulating expiry) and confirming the message is marked as expired in the log.

**Acceptance Scenarios**:

1. **Given** the user clicks Reject, **Then** the tailored resume is discarded, Slack shows a confirmation that the result was rejected, and the log records the session with a "Rejected" outcome.
2. **Given** no user response is received within 24 hours of the Slack message being sent, **Then** the message is marked as expired, no PDF is created, and the log records the session with an "Expired" outcome.
3. **Given** the user clicks Reject after one or more edit iterations, **Then** all versions of the tailored resume are discarded.

---

### Edge Cases

- What happens if the Slack message delivery fails after the resume is generated?
- What happens if a user responds to an already-expired Slack message?
- What happens if the AI tailoring produces a resume significantly longer or shorter than the base?
- What happens if the same job description is submitted multiple times in quick succession?
- What happens if PDF export fails after the user clicks Approve (network/disk issue)?
- What happens if the Slack thread receives a message from someone other than the authorised user?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST be invocable from the command line, accepting a job description as either direct text or a path to a local text file.
- **FR-002**: The tool MUST extract skills, required qualifications, and key terminology from the provided job description before tailoring begins.
- **FR-003**: The tool MUST tailor the user's stored base resume by reordering experience bullets to surface the most relevant achievements first, adjusting the professional summary to align with the role, and replacing or supplementing generic language with terminology from the job description.
- **FR-004**: The tailored resume MUST NOT introduce factual claims about skills, experience, or credentials that are not present in the user's base resume.
- **FR-005**: The tool MUST automatically score each tailored resume for keyword coverage—expressed as a percentage of identified job-description keywords present in the tailored resume.
- **FR-006**: The tool MUST automatically score each tailored resume for hallucination—identifying content in the tailored resume that has no basis in the base resume.
- **FR-007**: The tool MUST send the tailored resume and both scores to the user's configured Slack workspace as a message containing Approve, Edit, and Reject action buttons.
- **FR-008**: Clicking Approve MUST export the tailored resume as a PDF file saved to the user's configured local output directory, and confirm the file path in Slack.
- **FR-009**: Clicking Edit MUST open a reply thread in Slack where the user can describe desired changes in plain language.
- **FR-010**: The tool MUST apply the user's edit request and post the updated tailored resume—with fresh scores and action buttons—in the same Slack thread.
- **FR-011**: The edit-and-review loop MUST be capped at 3 iterations; after the 3rd iteration, only Approve and Reject buttons are shown.
- **FR-012**: Clicking Reject MUST discard all versions of the tailored resume and record a "Rejected" outcome in the log.
- **FR-013**: Slack messages that receive no user interaction within 24 hours MUST be automatically marked as expired, with an "Expired" outcome recorded in the log.
- **FR-014**: The tool MUST write a log entry for every completed session capturing: job description reference, keyword coverage score, hallucination score, number of edit iterations, user decision (Approved/Rejected/Expired), timestamp, and PDF output path (if approved).
- **FR-015**: The tool MUST validate that the base resume file and Slack configuration are present and accessible before processing any job description.

### Key Entities

- **Base Resume**: The user's master resume document stored locally as a structured text file; serves as the sole factual source for tailoring.
- **Job Description**: The input text describing the target role's requirements, responsibilities, and preferred qualifications.
- **Tailored Resume**: The AI-adapted version of the base resume for a specific job, preserving factual accuracy while optimising for relevance.
- **Quality Score**: A composite of keyword coverage percentage and hallucination assessment attached to each version of a tailored resume.
- **Edit Request**: A natural-language description of desired changes provided by the user in a Slack thread reply.
- **Session Log Entry**: A persisted record of one tailoring run, including scores, iteration count, user decision, and timing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The user receives a Slack review message within 2 minutes of providing the job description.
- **SC-002**: Edit requests are reflected in an updated resume posted to Slack within 90 seconds of the user submitting the request.
- **SC-003**: 100% of approved resumes result in a valid, complete PDF file saved to the output directory.
- **SC-004**: Every session (whether approved, rejected, or expired) has a corresponding log entry with all required fields populated.
- **SC-005**: Expired Slack messages are marked as such within 5 minutes of the 24-hour window closing.
- **SC-006**: Zero hallucinations (unverified factual claims) are present in any approved tailored resume, as validated by the hallucination score.

## Assumptions

- The user has a single base resume stored as a plain text or structured document file; its path is configured once at setup time.
- The user has a Slack workspace and a Slack bot app pre-configured before running the tool; Slack setup is out of scope for this feature.
- The tool is designed for a single user on a single machine; multi-user, team sharing, and cloud sync are out of scope.
- The job description is expected to be a complete posting (not a one-line query); very short or unstructured inputs may produce lower-quality tailoring.
- Hallucination is defined as: any factual claim in the tailored resume about skills, roles, achievements, or credentials that cannot be traced to the base resume.
- Keyword coverage scoring is informational and does not block Slack delivery regardless of the score.
- After 3 edit iterations, the user receives a final version with only Approve and Reject options; no automatic approval occurs.
- The PDF output directory defaults to the current working directory unless the user configures an alternative path.
- Each tailoring run is independent; edit iteration count resets for every new job description input.
- The tool does not retain Slack message state after a session concludes (Approved, Rejected, or Expired).
- The user interacting with Slack buttons is assumed to be the authorised single user; no authentication of button presses is enforced.
