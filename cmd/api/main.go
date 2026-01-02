// SpotiFLAC HTTP API Server
// Provides HTTP endpoints for the Telegram bot to communicate with the Go backend
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"spotiflac/backend"
	"strings"
	"time"
)

var (
	port        = flag.Int("port", 8765, "HTTP server port")
	downloadDir = flag.String("download-dir", "", "Default download directory")
)

func main() {
	flag.Parse()

	// Set default download directory
	if *downloadDir == "" {
		*downloadDir = filepath.Join(os.TempDir(), "spotiflac")
	}
	os.MkdirAll(*downloadDir, 0755)

	// Register handlers
	http.HandleFunc("/health", handleHealth)
	http.HandleFunc("/metadata", handleMetadata)
	http.HandleFunc("/download", handleDownload)
	http.HandleFunc("/lyrics", handleLyrics)
	http.HandleFunc("/cover", handleCover)
	http.HandleFunc("/check", handleCheck)
	http.HandleFunc("/search", handleSearch)
	http.HandleFunc("/analyze", handleAnalyze)

	addr := fmt.Sprintf(":%d", *port)
	log.Printf("SpotiFLAC API Server starting on %s", addr)
	log.Printf("Download directory: %s", *downloadDir)

	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}

// =============================================================================
// Health Check
// =============================================================================

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

// =============================================================================
// Metadata Endpoint
// =============================================================================

func handleMetadata(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	url := r.URL.Query().Get("url")
	if url == "" {
		http.Error(w, `{"error":"url parameter required"}`, http.StatusBadRequest)
		return
	}

	log.Printf("Fetching metadata for: %s", url)

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	result, err := backend.GetFilteredSpotifyData(ctx, url, false, 0)
	if err != nil {
		json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	json.NewEncoder(w).Encode(result)
}

// =============================================================================
// Download Endpoint
// =============================================================================

type DownloadRequest struct {
	ISRC           string `json:"isrc"`
	SpotifyID      string `json:"spotify_id"`
	TrackName      string `json:"track_name"`
	ArtistName     string `json:"artist_name"`
	AlbumName      string `json:"album_name"`
	AlbumArtist    string `json:"album_artist"`
	ReleaseDate    string `json:"release_date"`
	CoverURL       string `json:"cover_url"`
	TrackNumber    int    `json:"track_number"`
	DiscNumber     int    `json:"disc_number"`
	TotalTracks    int    `json:"total_tracks"`
	Source         string `json:"source"`
	Quality        string `json:"quality"`
	EmbedLyrics    bool   `json:"embed_lyrics"`
	EmbedMaxCover  bool   `json:"embed_max_cover"`
	OutputDir      string `json:"output_dir"`
	FilenameFormat string `json:"filename_format"`
}

type DownloadResponse struct {
	Success bool   `json:"success"`
	File    string `json:"file,omitempty"`
	Error   string `json:"error,omitempty"`
}

func handleDownload(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	if r.Method != http.MethodPost {
		http.Error(w, `{"error":"POST required"}`, http.StatusMethodNotAllowed)
		return
	}

	var req DownloadRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		json.NewEncoder(w).Encode(DownloadResponse{Success: false, Error: err.Error()})
		return
	}

	if req.ISRC == "" {
		json.NewEncoder(w).Encode(DownloadResponse{Success: false, Error: "ISRC required"})
		return
	}

	// Set defaults
	if req.OutputDir == "" {
		req.OutputDir = *downloadDir
	}
	if req.Source == "" {
		req.Source = "auto"
	}
	if req.FilenameFormat == "" {
		req.FilenameFormat = "{artist} - {title}"
	}

	log.Printf("Downloading track: %s - %s (ISRC: %s)", req.ArtistName, req.TrackName, req.ISRC)

	// Determine which service to use
	var filePath string
	var err error

	switch req.Source {
	case "tidal":
		filePath, err = downloadFromTidal(req)
	case "qobuz":
		filePath, err = downloadFromQobuz(req)
	case "amazon":
		filePath, err = downloadFromAmazon(req)
	default:
		// Auto: try Tidal first, then Qobuz, then Amazon
		filePath, err = downloadFromTidal(req)
		if err != nil {
			log.Printf("Tidal failed, trying Qobuz: %v", err)
			filePath, err = downloadFromQobuz(req)
		}
		if err != nil {
			log.Printf("Qobuz failed, trying Amazon: %v", err)
			filePath, err = downloadFromAmazon(req)
		}
	}

	if err != nil {
		json.NewEncoder(w).Encode(DownloadResponse{Success: false, Error: err.Error()})
		return
	}

	json.NewEncoder(w).Encode(DownloadResponse{Success: true, File: filePath})
}

func downloadFromTidal(req DownloadRequest) (string, error) {
	downloader := backend.NewTidalDownloader("")

	// Search for track by ISRC
	track, err := downloader.SearchTrackByMetadataWithISRC(req.TrackName, req.ArtistName, req.ISRC, 0)
	if err != nil {
		return "", err
	}

	quality := "LOSSLESS"
	if req.Quality != "" {
		quality = req.Quality
	}

	return downloader.DownloadByURL(
		fmt.Sprintf("https://tidal.com/track/%d", track.ID),
		req.OutputDir,
		quality,
		req.FilenameFormat,
		req.TrackNumber > 0,
		req.TrackNumber,
		req.TrackName,
		req.ArtistName,
		req.AlbumName,
		req.AlbumArtist,
		req.ReleaseDate,
		true,
		req.CoverURL,
		req.EmbedMaxCover,
		req.TrackNumber,
		req.DiscNumber,
		req.TotalTracks,
		req.ISRC,
	)
}

func downloadFromQobuz(req DownloadRequest) (string, error) {
	downloader := backend.NewQobuzDownloader()

	quality := "6" // Default to 16-bit FLAC
	if req.Quality != "" {
		quality = req.Quality
	}

	return downloader.DownloadByISRC(
		req.ISRC,
		req.OutputDir,
		quality,
		req.FilenameFormat,
		req.TrackNumber > 0,
		req.TrackNumber,
		req.TrackName,
		req.ArtistName,
		req.AlbumName,
		req.AlbumArtist,
		req.ReleaseDate,
		true,
		req.CoverURL,
		req.EmbedMaxCover,
		req.TrackNumber,
		req.DiscNumber,
		req.TotalTracks,
	)
}

func downloadFromAmazon(req DownloadRequest) (string, error) {
	downloader := backend.NewAmazonDownloader()

	// Get Amazon URL from Spotify ID first
	amazonURL, err := downloader.GetAmazonURLFromSpotify(req.SpotifyID)
	if err != nil {
		return "", err
	}

	return downloader.DownloadByURL(
		amazonURL,
		req.OutputDir,
		req.FilenameFormat,
		req.TrackNumber > 0,
		req.TrackNumber,
		req.TrackName,
		req.ArtistName,
		req.AlbumName,
		req.AlbumArtist,
		req.ReleaseDate,
		req.CoverURL,
		req.ISRC,
		req.TrackNumber,
		req.DiscNumber,
		req.TotalTracks,
		req.EmbedMaxCover,
	)
}

// =============================================================================
// Lyrics Endpoint
// =============================================================================

type LyricsRequest struct {
	SpotifyID  string `json:"spotify_id"`
	TrackName  string `json:"track_name"`
	ArtistName string `json:"artist_name"`
	AlbumName  string `json:"album_name"`
	OutputDir  string `json:"output_dir"`
}

func handleLyrics(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	if r.Method != http.MethodPost {
		http.Error(w, `{"error":"POST required"}`, http.StatusMethodNotAllowed)
		return
	}

	var req LyricsRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		json.NewEncoder(w).Encode(map[string]interface{}{"success": false, "error": err.Error()})
		return
	}

	if req.OutputDir == "" {
		req.OutputDir = *downloadDir
	}

	log.Printf("Downloading lyrics for: %s - %s", req.ArtistName, req.TrackName)

	client := backend.NewLyricsClient()
	lyricsReq := backend.LyricsDownloadRequest{
		SpotifyID:      req.SpotifyID,
		TrackName:      req.TrackName,
		ArtistName:     req.ArtistName,
		AlbumName:      req.AlbumName,
		OutputDir:      req.OutputDir,
		FilenameFormat: "{artist} - {title}",
		TrackNumber:    false,
		Position:       0,
	}

	result, err := client.DownloadLyrics(lyricsReq)

	if err != nil {
		json.NewEncoder(w).Encode(map[string]interface{}{"success": false, "error": err.Error()})
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": result.Success,
		"file":    result.File,
		"error":   result.Error,
	})
}

// =============================================================================
// Cover Endpoint
// =============================================================================

type CoverRequest struct {
	CoverURL   string `json:"cover_url"`
	TrackName  string `json:"track_name"`
	ArtistName string `json:"artist_name"`
	OutputDir  string `json:"output_dir"`
}

func handleCover(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	if r.Method != http.MethodPost {
		http.Error(w, `{"error":"POST required"}`, http.StatusMethodNotAllowed)
		return
	}

	var req CoverRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		json.NewEncoder(w).Encode(map[string]interface{}{"success": false, "error": err.Error()})
		return
	}

	if req.CoverURL == "" {
		json.NewEncoder(w).Encode(map[string]interface{}{"success": false, "error": "cover_url required"})
		return
	}

	if req.OutputDir == "" {
		req.OutputDir = *downloadDir
	}

	log.Printf("Downloading cover for: %s - %s", req.ArtistName, req.TrackName)

	filename := sanitizeFilenameSimple(fmt.Sprintf("%s - %s.jpg", req.ArtistName, req.TrackName))
	filePath := filepath.Join(req.OutputDir, filename)

	client := backend.NewCoverClient()
	err := client.DownloadCoverToPath(req.CoverURL, filePath, true)
	if err != nil {
		json.NewEncoder(w).Encode(map[string]interface{}{"success": false, "error": err.Error()})
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"file":    filePath,
	})
}

// =============================================================================
// Check Availability Endpoint
// =============================================================================

func handleCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	spotifyID := r.URL.Query().Get("spotify_id")
	isrc := r.URL.Query().Get("isrc")

	if spotifyID == "" {
		http.Error(w, `{"error":"spotify_id required"}`, http.StatusBadRequest)
		return
	}

	log.Printf("Checking availability for: %s", spotifyID)

	client := backend.NewSongLinkClient()
	result, err := client.CheckTrackAvailability(spotifyID, isrc)
	if err != nil {
		json.NewEncoder(w).Encode(map[string]interface{}{"error": err.Error()})
		return
	}

	json.NewEncoder(w).Encode(result)
}

// =============================================================================
// Search Endpoint
// =============================================================================

func handleSearch(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	query := r.URL.Query().Get("query")
	if query == "" {
		http.Error(w, `{"error":"query required"}`, http.StatusBadRequest)
		return
	}

	limit := 10
	if l := r.URL.Query().Get("limit"); l != "" {
		fmt.Sscanf(l, "%d", &limit)
	}

	log.Printf("Searching Spotify for: %s", query)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	result, err := backend.SearchSpotify(ctx, query, limit)
	if err != nil {
		json.NewEncoder(w).Encode(map[string]interface{}{"error": err.Error()})
		return
	}

	json.NewEncoder(w).Encode(result)
}

// =============================================================================
// Analyze Endpoint
// =============================================================================

func handleAnalyze(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	filePath := r.URL.Query().Get("file")
	if filePath == "" {
		http.Error(w, `{"error":"file parameter required"}`, http.StatusBadRequest)
		return
	}

	log.Printf("Analyzing file: %s", filePath)

	result, err := backend.AnalyzeTrack(filePath)
	if err != nil {
		json.NewEncoder(w).Encode(map[string]interface{}{"error": err.Error()})
		return
	}

	json.NewEncoder(w).Encode(result)
}

// =============================================================================
// Utilities
// =============================================================================

// sanitizeFilenameSimple removes invalid characters from filename
func sanitizeFilenameSimple(name string) string {
	// Remove characters not allowed in filenames
	invalid := regexp.MustCompile(`[<>:"/\\|?*]`)
	name = invalid.ReplaceAllString(name, "")

	// Trim spaces and dots
	name = strings.TrimSpace(name)
	name = strings.TrimRight(name, ".")

	if name == "" {
		name = "untitled"
	}

	return name
}
