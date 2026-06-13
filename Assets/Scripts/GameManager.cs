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

    void PickNextCountry()
    {
        if (countries.Count == 0) return;
        Country next;
        do { next = countries[Random.Range(0, countries.Count)]; }
        while (countries.Count > 1 && currentTarget != null && next.countryName == currentTarget.countryName);
        currentTarget = next;
    }

    public void OnFlagCaught(Country caught)
    {
        if (!gameActive) return;

        if (caught.countryName == currentTarget.countryName)
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

    void CheckGameOver()
    {
        if (lives <= 0)
        {
            gameActive = false;
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
}
