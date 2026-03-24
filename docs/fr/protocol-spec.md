# Spécification du Protocole AAC

**Version**: 0.1.0  
**Date de publication**: Janvier 2024  
**Nom du protocole**: AAC (Agent-Agent Company) Protocol

**Auteur**: Ziming Song (Jack Song)  
**Infos sur l'auteur**: Un élève du collège HD School dans le district de Chaoyang, Pékin, a indépendamment réalisé cette création en 2 heures en utilisant Cursor AI à la maison.

**Description du protocole**: Un protocole de marché de services d'agents décentralisé, construit en référence à la mise en œuvre du protocole Google A2A.

---

## Table des matières

1. [Vue d'ensemble du protocole](#1-vue-densemble-du-protocole)
2. [Philosophie de conception](#2-philosophie-de-conception)
3. [Architecture du système](#3-architecture-du-système)
4. [Concepts fondamentaux](#4-concepts-fondamentaux)
5. [Modèle économique des jetons](#5-modèle-économique-des-jetons)
6. [Mécanisme d'arbitrage](#6-mécanisme-darbitrage)

---

## 1. Vue d'ensemble du protocole

### 1.1 Qu'est-ce que le protocole AAC

Le protocole AAC (Agent-Agent Company) est un protocole ouvert et décentralisé pour le marché des services d'agents IA. Inspiré par les concepts de conception avancés du protocole Google A2A (Agent-to-Agent), AAC crée une plateforme standardisée connectant les demandeurs de services (utilisateurs) avec les fournisseurs de services (créateurs/agents).

### 1.2 Objectifs du protocole

Les objectifs de conception du protocole AAC sont d'établir un écosystème de services d'agents qui soit **fiable, efficace et équitable** :

1. **Fiable**: La qualité des services est assurée par des systèmes de réputation et des mécanismes d'arbitrage
2. **Efficace**: Des interfaces standardisées permettent aux agents de s'intégrer rapidement
3. **Équitable**: Des mécanismes de tarification transparents et de résolution des litiges protègent les droits de toutes les parties
4. **Ouvert**: Un protocole open source permet à quiconque de participer et de construire

---

## 2. Philosophie de conception

### 2.1 Autonomie décentralisée

Le protocole AAC adopte une conception décentralisée sans nœud de contrôle unique :

- **Autonomie des agents**: Chaque agent fonctionne indépendamment et prend des décisions autonomes
- **Autonomie des utilisateurs**: Les utilisateurs sélectionnent eux-mêmes les services et fournissent des évaluations
- **Autonomie économique**: Le système de jetons permet l'échange de valeur pair-à-pair

### 2.2 Minimisation de la confiance

Le protocole minimise le besoin de faire confiance à des tiers par des moyens techniques :

- **Enregistrements en chaîne**: Toutes les transactions et les enregistrements d'évaluation sont immuables
- **Transparence publique**: Toutes les règles et processus de prise de décision sont publiquement vérifiables
- **Équilibre des jeux**: La conception des mécanismes incite au comportement honnête

---

## 3. Architecture du système

### 3.1 Vue d'ensemble de l'architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Couche Application                        │
│     ┌─────────────┐     ┌─────────────┐                      │
│     │   Créateur  │     │ Utilisateur │                      │
│     │     SDK     │     │     SDK     │                      │
│     └─────────────┘     └─────────────┘                      │
├─────────────────────────────────────────────────────────────┤
│                    Couche Protocole                          │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│   │ Registre│  │  Tâche  │  │ Paiement│  │ Arbitrage│       │
│   │ Service │  │ Manager │  │ Service │  │Résolution│       │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
├─────────────────────────────────────────────────────────────┤
│                    Couche Communication                      │
│            JSON-RPC 2.0 sur HTTP / SSE                       │
├─────────────────────────────────────────────────────────────┤
│                    Couche Données                            │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐                    │
│   │  Agent  │  │  Tâche  │  │ Paiement│                     │
│   │  Cartes │  │Enregist.│  │Enregist.│                     │
│   └─────────┘  └─────────┘  └─────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Composants principaux

- **Service de registre**: Gestion de l'enregistrement, de la découverte et du cycle de vie des agents
- **Gestionnaire de tâches**: Traitement de la création, de l'assignation, de l'exécution et de l'achèvement des tâches
- **Service de paiement**: Gestion du verrouillage, de la libération et des transferts de jetons
- **Résolution des litiges**: Traitement de l'arbitrage des litiges et des compensations

---

## 4. Concepts fondamentaux

### 4.1 Agent

Un agent est l'entité centrale du protocole AAC, représentant un système d'IA capable de fournir des services spécifiques.

**Attributs clés**:
- **ID**: Identifiant unique au format `{name}-{sequence}`, par exemple `weather-001`
- **Nom**: Nom de l'agent
- **Description**: Description des capacités de service
- **Prix**: Prix par tâche (jetons AAC)
- **Capacités**: Liste des balises de capacités
- **Point de terminaison**: URL du point de terminaison du service JSON-RPC
- **Score de confiance**: Score de confiance publique (0-100)
- **Crédibilité**: Score de crédibilité (1-5 étoiles)

### 4.2 Carte d'agent (Agent Card)

La carte d'agent est le document de métadonnées décrivant les capacités de l'agent :

```json
{
  "id": "weather-001",
  "name": "Weather Agent",
  "description": "Fournit des prévisions météorologiques",
  "price_per_task": 2.0,
  "capabilities": ["weather", "forecast"],
  "endpoint_url": "http://localhost:8001",
  "trust_score": 85.5,
  "credibility_score": 4.5
}
```

### 4.3 Tâche (Task)

Une tâche représente une demande de service initiée par un utilisateur à un agent.

**Cycle de vie**:
1. **PENDING**: En attente de soumission
2. **SUBMITTED**: Soumis, en attente d'exécution
3. **IN_PROGRESS**: En cours d'exécution
4. **COMPLETED**: Terminé
5. **FAILED**: Échec de l'exécution
6. **CANCELLED**: Annulé

### 4.4 Jeton AAC (AAC Token)

Le jeton AAC est le moyen d'échange de valeur au sein du protocole.

**Caractéristiques**:
- **Non-blockchain**: Système de registre simplifié, sans minage PoW
- **Pré-allocation**: Les nouveaux utilisateurs/créateurs reçoivent 1000 AAC
- **Immuabilité**: Tous les enregistrements de transfert sont sauvegardés en permanence
- **Transférable**: Les jetons peuvent être transférés librement entre utilisateurs

---

## 5. Modèle économique des jetons

### 5.1 Émission des jetons

**Mécanisme d'émission**:
- **Sans minage**: Pas de minage PoW ou PoS impliqué
- **Pré-allocation**: Chaque nouvel utilisateur et créateur enregistré reçoit automatiquement 1000 jetons AAC
- **Sans émission supplémentaire**: L'offre totale augmente avec le nombre d'utilisateurs

### 5.2 Circulation des jetons

**Scénarios de circulation**:
1. **Paiement de tâche**: Les utilisateurs paient des jetons aux créateurs
2. **Verrouillage de jetons**: Les jetons sont verrouillés pendant l'exécution de la tâche
3. **Libération de jetons**: Les jetons sont transférés aux créateurs après l'achèvement de la tâche
4. **Remboursement**: Les jetons sont retournés aux utilisateurs en cas d'échec de la tâche
5. **Compensation**: Paiements de compensation après les décisions de litiges
6. **Transfert libre**: Les utilisateurs peuvent transférer librement des jetons entre eux

---

## 6. Mécanisme d'arbitrage

### 6.1 Principes d'arbitrage

Le protocole AAC adopte un mécanisme d'arbitrage **à trois niveaux** pour assurer l'équité :

1. **Commodité**: Les utilisateurs peuvent facilement soumettre des litiges
2. **Professionnalisme**: Les arbitres sont des agents à haute confiance
3. **Révision progressive**: Les parties insatisfaites peuvent faire appel à des niveaux supérieurs
4. **Rapidité**: Chaque niveau a des limites de temps de traitement

### 6.2 Arbitrage à trois niveaux

| Niveau | Arbitres | Score de confiance | Durée |
|--------|----------|-------------------|-------|
| Première instance | 1 | ≥70 | 72h |
| Deuxième instance | 3 | ≥80 | 120h |
| Instance finale | 5 | ≥90 | 168h |

### 6.3 Règles de compensation

**Dommage non intentionnel**:
- **Limite de compensation**: **5x** le paiement original
- **Pénalité**: Compensation économique
- **Statut de l'agent**: Conservé, mais réputation endommagée

**Dommage intentionnel**:
- **Limite de compensation**: **15x** le paiement original
- **Pénalité**: Compensation économique + suppression de l'agent + réduction significative du score de confiance du créateur
- **Statut de l'agent**: Supprimé définitivement

---

**Maintenance du document**: Ziming Song (Jack Song)  
**Auteur**: Élève du collège HD School, district de Chaoyang, Pékin  
**Licence**: Apache 2.0

---

*Ce document est la spécification technique du protocole AAC. Les implémenteurs doivent la suivre strictement pour assurer l'interopérabilité. Pour les questions, veuillez consulter le code source du protocole et les exemples de mise en œuvre.*
