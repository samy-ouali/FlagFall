using UnityEngine;

// =========================================================
// PlayerController : deplace le panier a gauche/droite.
// Place ce script sur le GameObject "Panier".
// Le panier a besoin d'un Collider2D coche en "Is Trigger" et d'un Tag "Player".
// =========================================================
public class PlayerController : MonoBehaviour
{
    [Header("Deplacement")]
    public float speed = 10f;
    public float screenBoundX = 7.5f;

    void Update()
    {
        // Fleches gauche/droite OU touches A/D
        float move = Input.GetAxis("Horizontal");
        Vector3 newPos = transform.position + Vector3.right * move * speed * Time.deltaTime;
        newPos.x = Mathf.Clamp(newPos.x, -screenBoundX, screenBoundX);
        transform.position = newPos;
    }
}
