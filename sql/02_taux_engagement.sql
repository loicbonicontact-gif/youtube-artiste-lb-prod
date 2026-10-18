-- Taux d'engagement par vidéo : (likes + commentaires) / vues
-- Utile pour LB Prod : une vidéo avec beaucoup de vues mais peu d'engagement
-- n'a pas le même intérêt promo qu'une vidéo qui génère beaucoup d'interactions.

SELECT
  title,
  view_count,
  like_count,
  comment_count,
  -- SAFE_DIVIDE évite une erreur si une vidéo a 0 vue
  SAFE_DIVIDE(like_count + comment_count, view_count) AS taux_engagement
FROM `api-au-tableau-de-bord.youtube_artiste.videos`
ORDER BY taux_engagement DESC
LIMIT 10;
