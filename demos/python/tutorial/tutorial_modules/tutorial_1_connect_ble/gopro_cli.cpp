#include <iostream>
#include <cstdlib>
#include <regex>
#include <vector>
#include <string>
#include <sstream>
#include <curl/curl.h>

// Function to check if the device responds to GoPro status endpoint
bool isGoproResponding(const std::string& ip) {
    CURL* curl = curl_easy_init();
    if (!curl) return false;

    std::string url = "http://" + ip + "/gp/gpControl/status";
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 500);
    curl_easy_setopt(curl, CURLOPT_NOBODY, 1L);

    CURLcode res = curl_easy_perform(curl);
    long response_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response_code);

    curl_easy_cleanup(curl);
    return (res == CURLE_OK && response_code == 200);
}

// Function to parse ARP table and find GoPro IPs
std::vector<std::string> discoverGoproIPs() {
    std::vector<std::string> goproIPs;
    FILE* pipe = popen("arp -a", "r");
    if (!pipe) return goproIPs;

    char buffer[256];
    std::regex goproMac("(30:23:03|a4:5e:60)", std::regex::icase);

    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        std::string line(buffer);
        std::regex ipRegex("\\(([^)]+)\\)");
        std::smatch match;

        if (std::regex_search(line, match, ipRegex)) {
            std::string ip = match[1];
            if (std::regex_search(line, goproMac)) {
                if (isGoproResponding(ip)) {
                    goproIPs.push_back(ip);
                }
            }
        }
    }

    pclose(pipe);
    return goproIPs;
}

int main() {
    curl_global_init(CURL_GLOBAL_DEFAULT);

    auto goproIPs = discoverGoproIPs();
    if (goproIPs.empty()) {
        std::cout << "No GoPros found on network.\n";
    } else {
        std::cout << "Discovered GoPro(s):\n";
        for (size_t i = 0; i < goproIPs.size(); ++i) {
            std::cout << "[" << i << "] " << goproIPs[i] << "\n";
        }
        // Example command: start recording
        std::string baseUrl = "http://" + goproIPs[0];
        std::string recordUrl = baseUrl + "/gp/gpControl/command/shutter?p=1";

        CURL* curl = curl_easy_init();
        curl_easy_setopt(curl, CURLOPT_URL, recordUrl.c_str());
        CURLcode res = curl_easy_perform(curl);
        if (res == CURLE_OK) {
            std::cout << "Started recording on GoPro." << std::endl;
        } else {
            std::cout << "Failed to start recording." << std::endl;
        }
        curl_easy_cleanup(curl);
    }

    curl_global_cleanup();
    return 0;
}
