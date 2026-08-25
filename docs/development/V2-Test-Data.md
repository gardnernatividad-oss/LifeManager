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

`backend/tests/postgres_safety.py` es la frontera común para cualquier test que
cree, migre, resetee o elimine una base. Exige intención de prueba explícita,
host loopback y uno de esos dos nombres exactos antes de crear un engine o
ejecutar DDL. `lifemanager` es la base local de desarrollo compartida y nunca
es un target desechable; estar en loopback no basta. Un target ambiguo,
preexistente, remoto o no allowlisted falla cerrado.

Los tests que invoquen Alembic deben construir su `Config` mediante
`alembic_config_for_test_database()`. El target explícito viaja en
`Config.attributes["database_url"]` y `alembic/env.py` le da precedencia sobre
la configuración de aplicación ya importada. No se debe cambiar únicamente una
variable de entorno después de importar `app.db.session`: `DATABASE_URL`,
`engine` y `SessionLocal` ya fueron materializados en ese momento.

## Seed de desarrollo

Stage 1.10 no añade un script de seed. Los builders ya satisfacen las necesidades inmediatas de pruebas sin introducir un ejecutable que pueda apuntar accidentalmente a una base equivocada. Si más adelante se necesita poblar manualmente una base de desarrollo, se deberá diseñar un comando separado con opt-in explícito, clasificación LOCAL y rechazo obligatorio de hosts remotos.

## Advertencia

Estos datos son exclusivamente para pruebas y desarrollo local. Nunca deben ejecutarse contra Neon, producción ni una base compartida. No se ejecutan al iniciar la aplicación y no incluyen credenciales, endpoints push ni datos personales reales.

En la validación inicial de Stage 3.4, un harness ad hoc cambió el entorno
después de importar `app.db.session`; Alembic reutilizó el `DATABASE_URL`
cacheado y aplicó el reset V2 a `lifemanager`. No había datos personales V2 en
uso autorizado y no se intentó restaurar V1. El incidente motivó la frontera
fail-closed anterior y la eliminación de `lifemanager` de la allowlist de la
migración destructiva.

Esta eliminación es una excepción explícita y acotada a la inmutabilidad de la
migración histórica `e4f5a6b7c8d9`: se realizó antes de producción para cerrar
también la ejecución manual directa de la revisión, una vía que no pasa por el
harness ni queda protegida por la selección de target en `alembic/env.py`. La
revisión, su parent y todo su DDL congelado permanecen idénticos; únicamente se
endureció la allowlist de su guarda previa a cualquier DDL. No se permiten más
cambios en esa migración por esta excepción.
