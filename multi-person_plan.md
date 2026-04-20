# Multi-Labeler Collaboration Plan

## Overview

This document describes the multi-person collaborative labeling workflow for dense datasets (60+ targets, 12+ classes per image). The goal is to distribute workload, ensure quality through overlap and voting, and handle conflicts automatically without requiring a dedicated reviewer role.

**Core Principle**: Tasks are class-centric (not image-centric). Each labeler specializes in 1-3 classes across the entire dataset.

---

## Big Picture Workflow

```
Admin prepares dataset
    ↓
Admin creates labeler accounts
    ↓
Admin creates tasks (by class or class group)
    ↓
Admin assigns tasks to labelers with overlap requirements
    ↓
Labelers label (single-class mode, low cognitive load)
    ↓
System continuously matches overlapping images
    ↓
If conflict detected:
    → Image assigned to additional labelers (3rd, 4th...)
    → Majority vote determines final label
    → Labelers with frequent conflicts get paused
    ↓
Admin collects results
    ↓
Statistics generated (per-labeler credits)
    ↓
Export final dataset
```

---

## 1. Accounts

### No passwords, no database
- First visit: pick username + role from a modal
- Stored in `localStorage`, sent as `X-Labeler` header with every request
- Admin can register labelers ahead of time via a simple JSON file (`labelers.json`)

### User Registry (`labelers.json`)
```json
{
  "alice": {"role": "labeler", "expertise": ["person", "vehicle"], "status": "active"},
  "bob": {"role": "labeler", "expertise": ["person"], "status": "active"},
  "charlie": {"role": "labeler", "expertise": ["vehicle"], "status": "paused"},
  "dave": {"role": "admin"}
}
```

**Status values**: `active` | `paused` 

---

## 2. Modes and Roles

### Roles (Permission Levels)

| Role | Can Do |
|------|--------|
| **Admin** | Create tasks, manage accounts, collect results, export data, view statistics |
| **Labeler** | Work on assigned tasks, label images, mark images complete |

**Note**: There is no dedicated "reviewer" role. Conflict resolution is handled automatically by assigning additional labelers and using majority voting.

### Task Modes (What the Labeler Does)

| Mode | Description | Use Case |
|------|-------------|----------|
| **`detect_single`** | Draw/adjust boxes. **Class is locked.** No class dropdown. | **Primary mode** — verify all people, all vehicles, etc. |
| **`detect_full`** | Draw boxes + pick class from allowed subset | Expert labeler handles related classes together |
| **`classify_only`** | Boxes are fixed. Only change class labels | Downstream refinement (e.g., person → worker/visitor) |
| **`verify`** | Flag correct/wrong. Minimal edits | Quality check on consensus |

---

## 3. Task Assignment and Overlap

### Admin Creates Tasks

Tasks split the dataset by **class or class group**, not by image slice.

**Example tasks for a 12-class human-centric dataset:**
- Task A: "Mark all people" (`detect_single`, class=`person`)
- Task B: "Mark all vehicles" (`detect_single`, classes=`car, truck, bus`)
- Task C: "Classify people by role" (`classify_only`, classes=`worker, visitor, security`)

### Overlap Strategy (Quality Control)

Every image must be labeled by **at least 2 labelers**.

**Initial Assignment:**
- Admin assigns tasks to labelers
- Each labeler gets a **percentage** of the dataset (e.g., 50%), not exact counts
- Images are randomly distributed with overlap

**Example for 2 labelers, 100 images:**
- Alice: images 1-60 (60%)
- Bob: images 41-100 (60%)
- Overlap: images 41-60 (20% of dataset, labeled by both)

**Why percentage, not exact counts?**
- Labelers may be assigned additional images if conflicts arise
- System dynamically adds more labelers to disputed images
- Percentages allow flexible redistribution

### Assignment Data (`assignments.json`)

```json
{
  "task_id": "task_001",
  "labelers": {
    "alice": {
      "target_percent": 50,
      "assigned_images": ["img_001", "img_002", "..."],
      "completed_images": ["img_001"]
    },
    "bob": {
      "target_percent": 50,
      "assigned_images": ["img_050", "img_051", "..."],
      "completed_images": []
    }
  },
  "image_assignments": {
    "img_001": {
      "labelers": ["alice", "bob"],
      "status": "in_progress",
      "conflict_level": "none"
    }
  }
}
```

---

## 4. Pre-label (Optional but Recommended)

Admin runs a detection model on all images.
- Boxes saved to `prelabels/` directory
- Not final labels — just a starting point
- Labelers can modify, delete, or add boxes

**Loading priority when a labeler opens an image:**
1. Their own saved work (`labels_by_user/{name}/`)
2. Pre-labels filtered to the task's class(es)
3. Empty canvas

---

## 5. Labeling Phase

### Labeler Workflow

1. Labeler logs in, sees their assigned tasks
2. Opens a task, gets first assigned image
3. Image loads with draft boxes (from pre-labels if available)
4. **No class dropdown** (in `detect_single` mode) — all boxes are automatically the task's class
5. Labeler refines: deletes false positives, adjusts boundaries, draws missed detections
6. Hits "Complete" → system saves to `labels_by_user/{name}/`

### What Happens on "Complete"

- Save labeler's work
- Check if this image has overlap with other labelers
- If ALL overlapping labelers have completed: **trigger matching immediately**
- If conflict detected: flag for additional labeling

---

## 6. Continuous Matching and Conflict Resolution

### Matching Runs Continuously

As soon as all assigned labelers finish an overlapping image, the system immediately:

1. Loads all labelers' annotations for that image
2. Runs IoU matching to pair boxes between labelers
3. Classifies each box into:
   - **Unanimous**: Found by all labelers with high IoU (auto-accept)
   - **Conflict**: Disagreement in position or missing detections

### Conflict Detection Criteria

A conflict is flagged when:
- Box found by one labeler but missed by another (no matching IoU > threshold)
- Same box but IoU < threshold between labelers (different boundaries)
- Class mismatch (only relevant in `detect_full` or `classify_only` modes)

### Conflict Resolution: Additional Labelers + Majority Vote

**When a conflict is detected:**

1. **Do NOT send to reviewer**
2. **Assign the image to additional labelers** (3rd, 4th, etc.)
3. Each new labeler labels the image independently
4. System re-runs matching with ALL labelers' data
5. **Majority vote determines the final result:**
   - For boxes: if 2 out of 3 labelers found a box in the same location → accept
   - For boundaries: average the coordinates of the majority group
   - For classes: plurality wins

**Example:**
- Alice: found box A at position (x1,y1)
- Bob: did NOT find box A
- System assigns to Charlie (3rd labeler)
- Charlie: found box A at position (x2,y2) close to Alice's
- Result: 2 out of 3 found box A → **Accept**, average position of Alice and Charlie

### Maximum Labelers per Image

- Default max: 5 labelers per image
- If conflict persists after 5 labelers → flag for admin manual review
- Admin can configure this threshold per task

---

## 7. Labeler Quality Monitoring and Pausing

### Conflict Tracking

System tracks per-labeler conflict statistics:
- Total images labeled
- Images where this labeler was in the minority (conflict loser)
- Conflict rate: `(conflict_losses / total_images) × 100%`

### Auto-Pause Threshold

If a labeler's conflict rate exceeds a threshold (default: 30%), their status changes to `paused`:

```json
{
  "alice": {
    "role": "labeler",
    "status": "active",
    "stats": {
      "images_labeled": 150,
      "conflicts_triggered": 12,
      "conflict_rate": 0.08
    }
  },
  "bob": {
    "role": "labeler",
    "status": "paused",
    "stats": {
      "images_labeled": 100,
      "conflicts_triggered": 35,
      "conflict_rate": 0.35,
      "pause_reason": "High conflict rate. Additional training required."
    }
  }
}
```

**What happens when paused:**
- Labeler cannot receive new assignments
- Their existing incomplete work remains
- Admin must manually reactivate after retraining
- Labeler sees a message: "Your labeling is paused. Please contact admin for retraining."

### Conflict Rate Calculation

```
conflict_rate = (times_labeler_was_in_minority) / (total_overlapping_images_labeled)
```

Only counts images where overlap matching occurred (not single-assigned images).

---

## 8. Data Structure

```
dataset/
  images/
  prelabels/              # Draft boxes from model (JSON)
  labels/                 # Final approved consensus (YOLO txt)
  labels_by_user/         # Per-labeler workspace
    alice/
    bob/
    charlie/
  tasks.json              # Task definitions
  assignments.json        # Task assignments and image allocation
  labelers.json           # User registry with stats
  metadata.json           # Dataset metadata
```

---

## 9. Admin Result Collection and Statistics

### Admin Dashboard

Admin can view real-time statistics:

**Per-Labeler Statistics:**
```json
{
  "alice": {
    "images_processed": 450,
    "targets_labeled": 28450,
    "tasks_completed": 3,
    "average_targets_per_image": 63.2,
    "conflict_rate": 0.08,
    "status": "active"
  },
  "bob": {
    "images_processed": 420,
    "targets_labeled": 26100,
    "tasks_completed": 2,
    "average_targets_per_image": 62.1,
    "conflict_rate": 0.35,
    "status": "paused"
  }
}
```

**Dataset Progress:**
- Total images: 1000
- Fully consensus-approved: 850
- Pending additional labelers (conflict): 120
- Awaiting initial labeling: 30

**Task Status:**
- Task A (person detection): 95% complete
- Task B (vehicle detection): 80% complete
- Task C (person classification): 0% complete (blocked until Task A done)

### Credit System

For payment or acknowledgment, the system tracks:
- **Images processed**: Count of images the labeler completed
- **Targets labeled**: Total bounding boxes drawn/adjusted
- **Consensus contributions**: Boxes that made it into final consensus
- **Conflict penalty**: Deducted from score if high conflict rate

**Credit formula:**
```
base_credit = (images_processed × image_rate) + (targets_labeled × target_rate)
quality_multiplier = max(0.5, 1.0 - conflict_rate)
final_credit = base_credit × quality_multiplier
```

---

## 10. Export

### Final Consensus Export

Admin exports the approved consensus from `labels/`:
- Standard YOLO format (`class_id x_center y_center width height`)
- Includes `metadata.json` with class names
- Quality report included (conflict rates, labeler credits, IAA scores)

### Export Options

1. **Full Consensus**: All approved labels from `labels/`
2. **High-Confidence Only**: Only unanimous labels (no conflicts ever)
3. **Per-Task Export**: Export only labels from specific tasks
4. **With Metadata**: Include quality report, labeler credits, conflict log

### Export Report Example

```json
{
  "export_date": "2024-01-20T15:30:00",
  "dataset_name": "crowd_dataset_v1",
  "total_images": 1000,
  "total_targets": 58420,
  "labelers": {
    "alice": {"images": 450, "targets": 28450, "credit_score": 0.92},
    "bob": {"images": 420, "targets": 26100, "credit_score": 0.65},
    "charlie": {"images": 380, "targets": 24200, "credit_score": 0.95}
  },
  "quality": {
    "average_conflict_rate": 0.12,
    "images_with_conflicts": 120,
    "unanimous_labels": 51200,
    "majority_vote_labels": 7220
  }
}
```

---

## 11. Key Design Principles

1. **Single-class tasks are the default** — reduces cognitive load, enables parallelization
2. **Pre-labels speed up work** — humans refine, not draw from scratch
3. **Tasks are class-centric, not image-centric** — Alice labels "people" across ALL images
4. **Overlap is mandatory** — every image gets at least 2 labelers
5. **Conflicts resolved by more labelers + majority vote** — no reviewer bottleneck
6. **Continuous matching** — matching runs as soon as overlapping labelers finish
7. **Dynamic redistribution** — labelers get percentages, exact counts shift based on conflicts
8. **Auto-pause for low quality** — high conflict rate = pause for retraining
9. **Transparent statistics** — every labeler sees their stats, admin sees all
10. **Backward compatible** — single-user mode still works without any changes

---

## 12. What This Gives You

| Before | After |
|--------|-------|
| One person labels 60 boxes × 12 classes per image | Multiple people each label 60 boxes × 1-3 classes per image |
| Every box needs class decision | Class is pre-locked by task |
| Start from blank canvas | Start from model-generated drafts |
| No quality check | Built-in overlap + majority vote + conflict tracking |
| One person must know all 12 classes | Each person specializes |
| Conflicts require manual review | Conflicts auto-resolve with additional labelers |
| No visibility into labeler quality | Real-time conflict rates and auto-pausing |
| No credit/tracking | Full statistics for payment and acknowledgment |
