# LedgerForge entity relationships

```mermaid
erDiagram
  DEPARTMENTS ||--o{ ROLES : contains
  DEPARTMENTS ||--o{ EMPLOYEES : current_department
  ROLES ||--o{ EMPLOYEES : current_role
  EMPLOYEES o|--o{ EMPLOYEES : manages
  EMPLOYEES ||--o{ EMPLOYEE_ASSIGNMENTS : has_history
  DEPARTMENTS ||--o{ EMPLOYEE_ASSIGNMENTS : assignment_department
  ROLES ||--o{ EMPLOYEE_ASSIGNMENTS : assignment_role
  EMPLOYEES o|--o{ EMPLOYEE_ASSIGNMENTS : assignment_manager
  EMPLOYEES ||--o{ SALARY_REVISIONS : receives
  ROLES ||--o{ SALARY_REVISIONS : role_after
  SALARY_REVISIONS ||--o{ SALARY_STRUCTURES : records
  SALARY_COMPONENTS ||--o{ SALARY_STRUCTURES : component
  EMPLOYEES ||--o{ SALARY_STRUCTURES : has
```

Employee `manager_id` points to another employee because a manager is also a person in the employee directory. It is nullable for top-level employees. Assignment rows preserve each employee's department, role, manager, and effective dates over time; the current employee fields are a convenient snapshot.

Legitimate nullable examples: `employees.exit_date` remains empty while the person is employed; `employees.manager_id` is empty for a top-level executive; `employee_assignments.effective_to` is empty on an assignment that is still active. `date_of_birth` can also be empty when not collected.

Salary revision `previous_annual_fixed`, `pct_change`, and `approved_by` are nullable because joining records have no previous salary or percentage change, and the supplied joining revisions have no approver recorded.
