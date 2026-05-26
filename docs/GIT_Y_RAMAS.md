# Guia practica de Git y ramas (OketaCup)

Este documento describe el flujo recomendado para trabajar con Git y GitHub en equipo, minimizando errores en merges y despliegues.

## Objetivo del flujo

- Desarrollo diario estable sobre `develop`.
- Produccion estable en `main`.
- Features aisladas en ramas propias.
- Historial claro y PRs faciles de revisar.

## Modelo de ramas recomendado

Ramas principales:
- `main`: codigo en produccion.
- `develop`: integracion de features listas para QA/staging.

Ramas temporales:
- `feature/<nombre-corto>`: nuevas funcionalidades.
- `fix/<nombre-corto>`: correcciones.
- `hotfix/<nombre-corto>`: correcciones urgentes sobre produccion.

Ejemplos:
- `feature/pool-scoring-v2`
- `fix/csrf-origin-prod`
- `hotfix/login-500-prod`

## Flujo completo para una feature

### 1) Actualiza `develop` local

```bash
git checkout develop
git pull origin develop
```

### 2) Crea tu rama de feature

```bash
git checkout -b feature/mi-feature
```

### 3) Trabaja y commitea en pequeno

```bash
git status
git add <archivos>
git commit -m "feat(pool): anade calculo de bonus por goles"
```

Buenas practicas de commit:
- Un commit = una idea concreta.
- Mensaje claro con prefijo (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`).
- Evitar commits gigantes con cambios mezclados.

### 4) Sincroniza con `develop` antes de abrir PR

Opcion recomendada (rebase limpio):

```bash
git fetch origin
git rebase origin/develop
```

Si hay conflictos:

```bash
# editar archivos
git add <archivo-resuelto>
git rebase --continue
```

### 5) Sube la rama

```bash
git push -u origin feature/mi-feature
```

### 6) Abre Pull Request hacia `develop`

En GitHub:
- Base: `develop`
- Compare: `feature/mi-feature`

Checklist de PR:
- Explicar que cambia y por que.
- Incluir pasos de prueba.
- Capturas/logs si aplica.
- Confirmar que CI pasa.

### 7) Merge de PR

Recomendacion:
- Usar `Squash and merge` para mantener historial compacto en `develop`.
- Borrar rama tras merge.

## Como pasar `develop` a `main` (release)

Proceso recomendado (con PR):

1. Asegurar que `develop` esta verde (tests/CI y validacion funcional).
2. Abrir PR `develop -> main`.
3. Revisar diff completo de release.
4. Merge en GitHub (idealmente `Create a merge commit` para dejar traza de release).
5. Etiquetar version (opcional pero recomendable), por ejemplo `v1.3.0`.

Comandos utiles para preparar release local:

```bash
git checkout main
git pull origin main
git checkout develop
git pull origin develop
```

## Hotfix en produccion

Si `main` esta rota y hay urgencia:

1. Crear rama desde `main`:
```bash
git checkout main
git pull origin main
git checkout -b hotfix/descripcion
```

2. Aplicar fix, commit, push y PR a `main`.
3. Tras merge en `main`, abrir PR de `main` a `develop` para no perder el fix.

## Comandos Git mas necesarios

Estado e historial:

```bash
git status
git log --oneline --graph --decorate -n 20
git diff
git diff --staged
```

Ramas:

```bash
git branch
git branch -a
git checkout develop
git checkout -b feature/nueva-rama
```

Sincronizacion:

```bash
git fetch origin
git pull origin develop
git push origin develop
```

Rebase/merge:

```bash
git rebase origin/develop
git merge develop
```

Deshacer sin destruir historial remoto:

```bash
git restore <archivo>
git restore --staged <archivo>
git revert <commit>
```

## Politicas recomendadas en GitHub

Configurar branch protection:
- `main` protegida.
- `develop` protegida (opcional segun equipo).
- Requerir PR para merge.
- Requerir checks de CI en verde.
- Bloquear force push en ramas protegidas.

## Reglas practicas de equipo

1. No trabajar directamente en `main`.
2. Evitar commits directos en `develop` (usar PR siempre que sea posible).
3. Actualizar tu rama con `develop` frecuentemente para reducir conflictos.
4. Resolver conflictos localmente y volver a ejecutar tests.
5. Mantener PRs pequenas (faciles de revisar).
6. Documentar cambios de despliegue en `docs/`.

## Flujo rapido resumido

1. `develop` actualizado.
2. Crear `feature/*`.
3. Commits pequenos y claros.
4. Rebase con `origin/develop`.
5. Push y PR a `develop`.
6. CI verde + review.
7. Merge.
8. Release periodica: PR `develop -> main`.

## Errores comunes y como evitarlos

- "Mi rama va muy atras":
  - `git fetch origin && git rebase origin/develop`

- "Me equivoque de rama al commitear":
  - crea rama nueva y mueve commit con `cherry-pick`.

- "Merge conflict grande al final":
  - integra `develop` con mas frecuencia (cada 1-2 dias).

- "Se desplego algo roto a main":
  - usar hotfix en `main` + back-merge a `develop`.
