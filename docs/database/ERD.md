# ERD de LifeManager

## Modelo objetivo de la Versión 1

El diagrama detallado del dominio de planificación y seguimiento se encuentra en:

```text
docs/database/V1-Target-Data-Model.md
```

Resumen conceptual:

```mermaid
erDiagram
    USER ||--o{ WORKSPACE_MEMBER : pertenece
    WORKSPACE ||--o{ WORKSPACE_MEMBER : contiene
    WORKSPACE ||--o{ CATEGORY : clasifica
    WORKSPACE ||--o{ PROJECT : contiene
    WORKSPACE ||--o{ TASK_SERIES : define
    WORKSPACE ||--o{ TASK : contiene
    WORKSPACE ||--o{ DAILY_CHECKLIST_SUBMISSION : registra
    WORKSPACE ||--o{ TRACKED_ITEM : contiene
    USER ||--o{ TASK : crea
    USER ||--o{ DAILY_CHECKLIST_SUBMISSION : envía
    USER ||--o{ TRACKED_ITEM_PROGRESS_UPDATE : registra
    CATEGORY ||--o{ PROJECT : clasifica
    CATEGORY ||--o{ TASK_SERIES : clasifica
    CATEGORY ||--o{ TASK : clasifica
    CATEGORY ||--o{ TRACKED_ITEM : clasifica
    PROJECT ||--o{ TASK_SERIES : agrupa
    PROJECT ||--o{ TASK : agrupa
    TASK_SERIES ||--o{ TASK : genera
    TRACKED_ITEM ||--o{ TRACKED_ITEM_PROGRESS_UPDATE : conserva
```

`Task` representa tanto Tareas manuales como ocurrencias generadas. `TaskSeries` siempre define una recurrencia finita mediante `start_date` y `end_date` obligatorias.
