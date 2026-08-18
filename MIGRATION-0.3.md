# Migration vers RAG Lab 0.3.0

RAG Lab 0.3.0 normalise l'identité publique du produit sans supprimer le moteur historique `rag-quality-bench`.

## État

Cette version est **PREPARED**, pas publiée. Une CI verte ou une attestation valide ne crée ni tag ni release.

## Identité canonique

- Produit/dépôt : **RAG Lab** / `vigilanty0x/rag-lab`.
- Distribution conservée pour compatibilité : `rag-quality-bench`.
- Namespace Python canonique : `import rag_lab`.
- CLI canonique : `rag-lab`.
- Interfaces historiques conservées : `import rag_quality_bench` et `rag-quality-bench`.

Les surfaces canoniques et historiques exposent exactement la même version `0.3.0` et les mêmes types publics du moteur d'évaluation.

## Compatibilité

Aucune migration de données n'est nécessaire. Les suites, rapports schema 1.0/2.0, manifests d'index et commandes historiques continuent d'utiliser le même moteur.

Nouveau code :

```python
import rag_lab
print(rag_lab.__version__)
```

Code historique toujours pris en charge :

```python
import rag_quality_bench
print(rag_quality_bench.__version__)
```

Les deux CLIs restent valides :

```bash
rag-lab probe --level functional
rag-quality-bench probe --level functional
```

## Release gates

Avant toute publication 0.3, le SHA approuvé doit avoir :

1. CI multi-OS/runtime complète ;
2. wheel et sdist construits et testés comme artefacts installés ;
3. contre-preuve fonctionnelle préservée ;
4. checksums SHA-256 et SBOM CycloneDX ;
5. provenance GitHub/Sigstore générée puis vérifiée ;
6. inventaire consommateurs et compatibilité des anciens points d'entrée ;
7. décision explicite de publication ;
8. vérification post-publication du tag, des artefacts, checksums et provenance.

La publication n'est pas implémentée dans la CI normale de cette migration.

## Rollback

Le rollback est le code/release 0.2.0 avec les interfaces historiques `rag-quality-bench` et `rag_quality_bench`.

Aucun schéma de base de données, état distant ou secret n'est modifié par 0.3. Un rollback consiste donc à réinstaller ou revenir au wheel 0.2.0 vérifié puis à utiliser les anciens points d'entrée si nécessaire.

## Archive gate

Les huit dépôts importés sous `packages/` ne sont pas archivés par cette migration. Tout archivage futur nécessite : inventaire consommateurs, compatibilité ou redirects, rollback vérifié et approbation humaine explicite.
