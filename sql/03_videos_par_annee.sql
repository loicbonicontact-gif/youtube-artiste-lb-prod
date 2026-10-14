-- Nombre de vidéos et vues totales par année de publication
-- Utile pour LB Prod : voir l'évolution de la fréquence de sortie et de
-- l'audience de Wilson au fil des années (analyse dans le temps).
--
-- TIMESTAMP(published_at) : published_at est redevenu du texte en passant
-- par le CSV, on le reconvertit en vraie date avant de pouvoir extraire l'année.

SELECT
  EXTRACT(YEAR FROM TIMESTAMP(published_at)) AS annee,
  COUNT(*) AS nb_videos,
  SUM(view_count) AS vues_totales
FROM `api-au-tableau-de-bord.youtube_artiste.videos`
GROUP BY annee
ORDER BY annee;
