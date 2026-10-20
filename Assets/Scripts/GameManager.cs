using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using TMPro;

// =========================================================
// GameManager : cerveau central du jeu (score, vies, pays demande).
// Place ce script sur un GameObject vide nomme "GameManager" dans la scene.
// =========================================================
public class GameManager : MonoBehaviour
{
    public static GameManager Instance;

    [Header("Pays (a remplir dans l'Inspector)")]
    public List<Country> countries = new List<Country>();

    [Header("References UI")]
    public TMP_Text scoreText;
    public TMP_Text countryText;
    public TMP_Text livesText;
    public GameObject gameOverPanel;
    public TMP_Text finalScoreText;

    [Header("Spawner (a glisser depuis la Hierarchie)")]
    public FlagSpawner spawner;

    [Header("Trophée 3D")]
    public GameObject trophee3D;

    private int score = 0;
    private int lives = 3;
    private Country currentTarget;
    private bool gameActive = true;

    void Awake()
    {
        if (Instance == null) Instance = this;
        else { Destroy(gameObject); return; }

        // Composants ML : ajoutes automatiquement s'ils ne sont pas deja sur l'objet.
        if (GetComponent<AdaptiveDirector>() == null) gameObject.AddComponent<AdaptiveDirector>();
        if (GetComponent<GameLogger>() == null) gameObject.AddComponent<GameLogger>();
    }

    void Start()
    {
        if (gameOverPanel != null) gameOverPanel.SetActive(false);
        if (trophee3D != null) trophee3D.SetActive(false);
        PickNextCountry();
        UpdateUI();
    }

    public Country GetCurrentTarget() { return currentTarget; }

    public Country GetRandomCountry()
    {
        return countries[Random.Range(0, countries.Count)];
    }

    // Faux drapeau a faire tomber : choisi par l'AdaptiveDirector s'il est present
    // (drapeaux ressemblants quand le joueur reussit bien), sinon au hasard.
    public Country GetDistractor()
    {
        if (AdaptiveDirector.Instance != null)
            return AdaptiveDirector.Instance.PickDistractor(currentTarget, countries);
        return GetRandomCountry();
    }

    void PickNextCountry()
    {
        if (countries.Count == 0) return;
        if (AdaptiveDirector.Instance != null)
        {
            // Pays choisi selon le niveau du joueur (ou au hasard si le mode adaptatif est desactive).
            currentTarget = AdaptiveDirector.Instance.PickTarget(countries, currentTarget);
        }
        else
        {
            Country next;
            do { next = countries[Random.Range(0, countries.Count)]; }
            while (countries.Count > 1 && currentTarget != null && next.countryName == currentTarget.countryName);
            currentTarget = next;
        }
        if (GameLogger.Instance != null) GameLogger.Instance.LogTargetShown(currentTarget);
    }

    public void OnFlagCaught(Country caught)
    {
        if (!gameActive) return;

        bool correct = caught.Code == currentTarget.Code;

        // Donnees pour le ML : tous les drapeaux visibles au moment de la capture.
        if (GameLogger.Instance != null)
            GameLogger.Instance.LogCatch(currentTarget, caught, FlagsOnScreen(), CurrentFallSpeed());
        if (AdaptiveDirector.Instance != null)
            AdaptiveDirector.Instance.Record(currentTarget, correct);

        if (correct)
        {
            score += 10;
            PickNextCountry();
        }
        else
        {
            score = Mathf.Max(0, score - 2);
            lives--;
            CheckGameOver();
        }
        UpdateUI();
    }

    // Appele par un drapeau qui sort de l'ecran sans avoir ete attrape.
    public void OnFlagMissed(Country missed)
    {
        if (!gameActive || missed == null || currentTarget == null) return;
        if (missed.Code == currentTarget.Code && GameLogger.Instance != null)
            GameLogger.Instance.LogTargetMissed(currentTarget, CurrentFallSpeed());
    }

    List<Country> FlagsOnScreen()
    {
        var list = new List<Country>();
        foreach (var f in FindObjectsByType<Flag>(FindObjectsSortMode.None))
            if (f.Country != null) list.Add(f.Country);
        return list;
    }

    float CurrentFallSpeed()
    {
        return spawner != null ? spawner.CurrentSpeed : -1f;
    }

    void CheckGameOver()
    {
        if (lives <= 0)
        {
            gameActive = false;
            if (GameLogger.Instance != null) GameLogger.Instance.LogGameOver(score);
            if (gameOverPanel != null) gameOverPanel.SetActive(true);
            if (trophee3D != null) trophee3D.SetActive(true);
            if (finalScoreText != null) finalScoreText.text = "Score final : " + score;
            if (spawner != null) spawner.enabled = false;
        }
    }

    void UpdateUI()
    {
        if (scoreText != null) scoreText.text = "Score : " + score;
        if (countryText != null && currentTarget != null) countryText.text = "Attrape : " + currentTarget.countryName;
        if (livesText != null) livesText.text = "Vies : " + new string('♥', Mathf.Max(0, lives));
    }

    // Bouton "Rejouer" sur le panneau Game Over : assigne RestartGame() dans l'Inspector.
    public void RestartGame()
    {
        SceneManager.LoadScene(SceneManager.GetActiveScene().name);
    }
}

// Classe simple pour stocker un pays + son drapeau.
[System.Serializable]
public class Country
{
    public string countryName;
    public Sprite flag;

    // Code du pays = nom du fichier image ("fr" pour Assets/Flags/fr.png).
    // C'est l'identifiant utilise par le modele ML et dans les logs.
    public string Code
    {
        get
        {
            if (flag == null) return countryName;
            return flag.texture != null ? flag.texture.name : flag.name.Split('_')[0];
        }
    }
}
