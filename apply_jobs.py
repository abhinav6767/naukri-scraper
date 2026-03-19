import json
import time
import random
import traceback
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

def get_edge_driver():
    edge_options = Options()
    edge_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    try:
        driver = webdriver.Edge(options=edge_options)
        return driver
    except Exception as e:
        print("[ERROR] Error connecting to Edge. Ensure it is running with --remote-debugging-port=9222")
        return None

def human_delay(min_secs=2, max_secs=5):
    time.sleep(random.uniform(min_secs, max_secs))

def apply_to_job(driver, job):
    jd_url = "https://www.naukri.com" + job.get('jdURL', '')
    if not job.get('jdURL'):
        return "No JD URL"
        
    print(f"\nNavigating to: {job.get('title')} at {job.get('companyName')}")
    
    try:
        # Switch to the first window handle just in case user opened new tabs
        if driver.window_handles:
            driver.switch_to.window(driver.window_handles[0])
            
        driver.get(jd_url)
    except Exception as e:
        print(f"Error navigating: {e}")
        # Try JS fallback
        try:
            driver.execute_script(f"window.location.href='{jd_url}';")
        except Exception as e2:
            print(f"JS Navigation also failed: {e2}")
            return "Navigation Failed"
            
    human_delay(4, 7) # Wait for page to fully load
    
    try:
        # Looking for the apply button
        apply_btn = WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'applied')]"))
        )
        
        btn_text = apply_btn.text.strip().lower()
        if 'applied' in btn_text:
            print("Already applied in the past. Skipping.")
            return "Already Applied"
        
        if 'company site' in btn_text:
            print("Job requires applying on company site. Skipping for automation safety.")
            return "Skipped (Company Site)"
            
        # Scroll to button and click
        driver.execute_script("arguments[0].scrollIntoView(true);", apply_btn)
        human_delay(1, 2)
        
        try:
            apply_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", apply_btn)
            
        print("[SUCCESS] Clicked Apply!")
        human_delay(3, 5) # wait for modal/questionnaire or success state
        
        # Switch to new tab if Naukri opened the application flow in a popup
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            human_delay(1, 2)
        
        # Check for Questionnaire
        try:
            questions = driver.find_elements(By.XPATH, "//div[contains(@class, 'chat') or contains(@class, 'bot')]//input | //textarea | //*[@id='custom_questions']")
            if len(questions) > 0:
                print("[WARN] Questionnaire detected!")
                return "Questionnaire Detected"
        except Exception:
            pass
            
        # If no questionnaire, check if application was successful
        try:
            page_src = driver.page_source.lower()
            page_title = driver.title.lower()
            curr_url = driver.current_url.lower()
            
            if "apply confirmation" in page_title or "applied to" in page_src or "successfully applied" in page_src or "applied successfully" in page_src or "naukri.com/myapply" in curr_url:
                print("[SUCCESS] Application Successful!")
                return "Success"
        except:
            pass

        return "Questionnaire Detected"

    except TimeoutException:
        # Perhaps already applied?
        try:
            already_applied = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'already applied') or text()='Applied' or text()='applied']")
            if len(already_applied) > 0:
                print("Information: Already applied to this job.")
                return "Already Applied"
        except NoSuchElementException:
            pass
        print("[ERROR] Apply button not found. Could not apply.")
        return "Failed (Apply Button Not Found)"
    except Exception as e:
        print("Error applying:")
        import traceback
        traceback.print_exc()
        return "Failed (Error)"

def main():
    print("Loading jobs from naukri_jobs.json...")
    try:
        with open('naukri_jobs.json', 'r', encoding='utf-8') as f:
            jobs = json.load(f)
    except FileNotFoundError:
        print("naukri_jobs.json not found!")
        return

    print(f"Loaded {len(jobs)} jobs.")
    
    driver = get_edge_driver()
    if not driver:
        return
        
    print("✅ Successfully connected to Microsoft Edge!")
    
    results = []
    test_jobs = jobs[:3]
    
    for idx, job in enumerate(test_jobs):
        status = apply_to_job(driver, job)
        results.append({"jobId": job.get("jobId"), "company": job.get("companyName"), "status": status})
        
        if status == "Questionnaire Detected":
            print("Stopping automation because manual intervention is required for a questionnaire.")
            break
            
        wait_time = random.uniform(5, 8)
        print(f"Waiting {wait_time:.1f} seconds before next job...")
        time.sleep(wait_time)
        
    print("\n--- Summary ---")
    for r in results:
        print(f"{r['company']}: {r['status']}")

if __name__ == "__main__":
    main()
