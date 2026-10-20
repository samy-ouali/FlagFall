using UnityEngine;

// =========================================================
// Flag : un drapeau qui tombe.
// Place ce script sur le prefab "Flag" (avec SpriteRenderer + Collider2D "Is Trigger").
// =========================================================
[RequireComponent(typeof(SpriteRenderer))]
public class Flag : MonoBehaviour
{
    public float fallSpeed = 3f;
    private Country country;
    private SpriteRenderer sr;

    public Country Country { get { return country; } }

    void Awake()
    {
        sr = GetComponent<SpriteRenderer>();
    }

    // Appele par le FlagSpawner juste apres l'instantiation.
    public void Setup(Country c, float speed)
    {
        country = c;
        fallSpeed = speed;
        if (sr != null && c != null && c.flag != null)
            sr.sprite = c.flag;
    }

    void Update()
    {
        transform.position += Vector3.down * fallSpeed * Time.deltaTime;

        // Si le drapeau passe sous l'ecran, on le detruit.
        if (transform.position.y < -6f)
        {
            if (GameManager.Instance != null)
                GameManager.Instance.OnFlagMissed(country);
            Destroy(gameObject);
        }
    }

    void OnTriggerEnter2D(Collider2D other)
    {
        if (other.CompareTag("Player"))
        {
            if (GameManager.Instance != null)
                GameManager.Instance.OnFlagCaught(country);
            Destroy(gameObject);
        }
    }
}
