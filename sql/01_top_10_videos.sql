-- Top 10 des vidéos les plus vues
-- Utile pour LB Prod : savoir quels titres de Wilson ont le mieux marché,
-- pour s'en inspirer sur les prochaines sorties.

SELECT *
FROM `api-au-tableau-de-bord.youtube_artiste.videos`
ORDER BY view_count DESC
LIMIT 10;
