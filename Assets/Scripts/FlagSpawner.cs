using UnityEngine;

// =========================================================
// FlagSpawner : fait apparaitre des drapeaux a intervalle regulier.
// Place ce script sur un GameObject vide nomme "Spawner".
// =========================================================
public class FlagSpawner : MonoBehaviour
{
    [Header("Reference au prefab du drapeau")]
    public GameObject flagPrefab;

    [Header("Zone d'apparition")]
    public float minX = -7f;
    public float maxX = 7f;
    public float startY = 6f;

    [Header("Reglages de base")]
    [Tooltip("Temps entre 2 apparitions au debut.")]
    public float spawnInterval = 1.5f;
    [Tooltip("Vitesse de chute initiale.")]
    public float fallSpeed = 3f;
    [Tooltip("Probabilite que le drapeau qui apparait soit le bon (entre 0 et 1).")]
    [Range(0f, 1f)]
    public float chanceCorrectFlag = 0.35f;

    [Header("Adaptativite : difficulte croissante")]
    [Tooltip("Vitesse de chute en plus par seconde de jeu.")]
    public float speedIncreasePerSecond = 0.05f;
    [Tooltip("Reduction de l'intervalle de spawn par seconde de jeu.")]
    public float intervalDecreasePerSecond = 0.01f;
    public float minInterval = 0.5f;

    private float timer;
    private float gameTime;

    // Vitesse de chute actuelle (enregistree dans les logs).
    public float CurrentSpeed { get { return fallSpeed + speedIncreasePerSecond * gameTime; } }

    void Update()
    {
        gameTime += Time.deltaTime;
        timer += Time.deltaTime;

        float currentInterval = Mathf.Max(minInterval, spawnInterval - intervalDecreasePerSecond * gameTime);
        float currentSpeed = CurrentSpeed;

        if (timer >= currentInterval)
        {
            timer = 0f;
            SpawnFlag(currentSpeed);
        }
    }

    void SpawnFlag(float speed)
    {
        if (GameManager.Instance == null || flagPrefab == null) return;

        Country target = GameManager.Instance.GetCurrentTarget();
        // Faux drapeau choisi par le GameManager (adaptatif si l'AdaptiveDirector est present).
        Country toSpawn = (Random.value < chanceCorrectFlag) ? target : GameManager.Instance.GetDistractor();

        Vector3 pos = new Vector3(Random.Range(minX, maxX), startY, 0f);
        GameObject obj = Instantiate(flagPrefab, pos, Quaternion.identity);
        Flag f = obj.GetComponent<Flag>();
        if (f != null) f.Setup(toSpawn, speed);
    }
}
