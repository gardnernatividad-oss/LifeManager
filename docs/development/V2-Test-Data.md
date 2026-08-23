# Datos de prueba de LifeManager V2

## Estado

Vigente para la base de persistencia de LifeManager V2.0.0 desde Stage 1.10.

## Arquitectura

Los factories viven en `backend/tests/factories/v2.py`. Son helpers explícitos de Python construidos sobre los modelos SQLAlchemy aprobados; no constituyen una capa de servicios ni implementan reglas de negocio de las APIs.

`V2Factory` recibe obligatoriamente una `Session` creada por el llamador. Sus responsabilidades son:

- crear objetos con identidades de prueba deterministas y únicas dentro del escenario;
- usar direcciones reservadas `example.test` y datos evidentemente ficticios;
- agregar objetos a la sesión;
- mantener coherentes las claves de Workspace y las relaciones entre entidades.

Los factories de bajo nivel no hacen `flush`, `commit` ni `rollback`. Los builders de escenarios pueden hacer `flush` para validar el grafo y obtener valores generados por la base. El llamador siempre conserva la propiedad de la transacción y decide si confirma o revierte.

Ningún factory crea un engine, lee `DATABASE_URL` ni desactiva restricciones. Los casos negativos deben construir datos inválidos explícitamente en su propio test.

## Escenarios reutilizables

- `personal_workspace()` crea un usuario activo, su Personal Workspace y la membresía activa del propietario.
- `shared_workspace()` crea un Shared Workspace con propietario, tres miembros activos y las tres configuraciones de privacidad de calendario.
- Los métodos de entidad cubren estados de cuenta y membresía, invitaciones, catálogos, Tasks, GenerationBatch, Pending Items e historial, Projects/Stages e historial, Activities, participantes, recordatorios, metadatos de Review, preferencias, notificaciones, suscripciones push y entregas.
- `build_canonical_dataset()` crea un grafo pequeño de varios usuarios y Workspaces, pensado para futuras pruebas de integración y E2E.

El dataset canónico incluye tres usuarios A/B/C con Personal Workspace. A es propietario y B/C son miembros de un Shared Workspace familiar ficticio; un cuarto miembro D completa el escenario compartido de propietario más tres miembros. Los mismos usuarios se reutilizan entre ambos contextos para que las futuras pruebas puedan comprobar aislamiento y acceso multi-Workspace.

## Uso

```python
def test_scenario(db: Session) -> None:
    dataset = V2Factory(db).build_canonical_dataset()
    assert dataset.shared_workspace.workspace.kind == WorkspaceKind.SHARED
    db.rollback()
```

En pruebas PostgreSQL, `db` debe apuntar exclusivamente a una base local y desechable incluida en la allowlist de tests (`lifemanager_test` o `lifemanager_v2_test`). El test de integración de fixtures se omite si no recibe una URL local y permitida.

## Seed de desarrollo

Stage 1.10 no añade un script de seed. Los builders ya satisfacen las necesidades inmediatas de pruebas sin introducir un ejecutable que pueda apuntar accidentalmente a una base equivocada. Si más adelante se necesita poblar manualmente una base de desarrollo, se deberá diseñar un comando separado con opt-in explícito, clasificación LOCAL y rechazo obligatorio de hosts remotos.

## Advertencia

Estos datos son exclusivamente para pruebas y desarrollo local. Nunca deben ejecutarse contra Neon, producción ni una base compartida. No se ejecutan al iniciar la aplicación y no incluyen credenciales, endpoints push ni datos personales reales.
