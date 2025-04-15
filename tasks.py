from dataclasses import dataclass
from pathlib import Path

from robocorp import browser
from robocorp.tasks import task
from RPA.HTTP import HTTP
from RPA.Tables import Tables
from RPA.PDF import PDF
from RPA.Archive import Archive

@task
def order_robots_from_RobotSpareBin() -> None:
    """
    Orders robots from RobotSpareBin Industries Inc.
    Saves the order HTML receipt as a PDF file.
    Saves the screenshot of the ordered robot.
    Embeds the screenshot of the robot to the PDF receipt.
    Creates ZIP archive of the receipts and the images.
    """
    # browser.configure(
    #     slowmo=500,
    # )
    config = Config()
    download_file(config.orders_file_url, config.orders_file_name)
    orders = get_orders(config)
    open_robot_order_website(config)
    close_annoying_modal()
    fill_and_submit_sales_form(orders, config)
    archive_receipts(config)

@dataclass
class Order:
    order_number: int
    head: str
    body: str
    legs: str
    address: str

@dataclass
class Config:
    """
    Config for the RobotSpareBin Industries Inc.
    """
    robot_order_website_url: str = "https://robotsparebinindustries.com/#robot-order"
    orders_file_url: str = "https://robotsparebinindustries.com/orders.csv"
    orders_file_name: str = "orders.csv"
    output_dir: Path = Path("output")

def embed_screenshot_to_receipt(screenshot_file: str, pdf_file: str):
    """
    Embeds the screenshot of the robot to the PDF receipt.
    """
    pdf = PDF()
    pdf.add_watermark_image_to_pdf(
        image_path=screenshot_file, 
        source_path=pdf_file, 
        output_path=pdf_file
    )

def archive_receipts(config: Config):
    """
    Archives the receipts.
    """
    archive = Archive()
    archive.archive_folder_with_zip(
        str(config.output_dir.joinpath("receipts").absolute()),
        str(config.output_dir.joinpath("receipts.zip").absolute())
    )
    
def store_receipt_as_pdf(order: Order, config: Config):
    """
    Stores the receipt as a PDF file.
    """
    receipt_pdf = PDF()
    screenshot_file = screenshot_robot(order, config)
    receipt_html = browser.page().locator("#receipt").inner_html()
    receipt_file = config.output_dir.joinpath("receipts").joinpath(f"receipt-{order.order_number}.pdf").absolute()
    receipt_pdf.html_to_pdf(receipt_html, receipt_file)
    embed_screenshot_to_receipt(screenshot_file, receipt_file)

def await_robot_preview(head: str, body: str, legs: str, timeout: int = 5000) -> None:
    """
    Waits for the robot preview to show specific parts.
    
    Args:
        head (str, optional): The head part number to wait for
        body (str, optional): The body part number to wait for
        legs (str, optional): The legs part number to wait for
        timeout (int, optional): Timeout in milliseconds
    """
    # Wait for the container first
    browser.page().wait_for_selector("#robot-preview-image", state="visible", timeout=timeout)
    
    # Wait for specific parts if provided
    if head:
        browser.page().wait_for_selector(f"#robot-preview-image img[src='/heads/{head}.png']", 
                                         state="visible", timeout=timeout)
    if body:
        browser.page().wait_for_selector(f"#robot-preview-image img[src='/bodies/{body}.png']", 
                                         state="visible", timeout=timeout)
    if legs:
        browser.page().wait_for_selector(f"#robot-preview-image img[src='/legs/{legs}.png']", 
                                         state="visible", timeout=timeout)

def screenshot_robot(order: Order, config: Config) -> str:
    """
    Takes a screenshot of the robot.
    """
    file_name = f"robot-{order.order_number}.png"
    full_path = config.output_dir.joinpath("screenshots").joinpath(file_name).absolute()
    # Wait for the "Order another robot" button to be visible
    await_robot_preview(order.head, order.body, order.legs)
    browser.page().screenshot(path=full_path)
    return full_path

def fill_and_submit_sales_form(orders: list[Order], config: Config) -> None:
    """
    Fills and submits the sales form for each order.
    """
    for order in orders:
        fill_order_form(order)
        submit_order()
        store_receipt_as_pdf(order, config)
        go_back_to_order_form()
        close_annoying_modal()

def fill_order_form(order: Order) -> None:
    """
    Fills the order form for the given order.
    """
    browser.page().select_option("#head", order.head)
    browser.page().click(f"#id-body-{order.body}")
    browser.page().fill("input.form-control[type='number']", order.legs)
    browser.page().fill("#address", order.address)

def submit_order() -> None:
    """
    Submits the order.
    """
    success = False
    max_retries = 3
    retry_count = 0
    click_order = lambda: browser.page().click("button:text('Order')", timeout=1000)
    wait_for_receipt = lambda: browser.page().wait_for_selector("#receipt", state="visible", timeout=1000)
    try:
        click_order()
        wait_for_receipt()
    except Exception as e:
         while not success:
            retry_count += 1
            if retry_count <= max_retries:
                # If we've exhausted all retries, try an alternative approach
                try:
                    click_order()
                    wait_for_receipt()
                    success = True
                except Exception:
                    pass
            else:
                raise Exception(f"Failed to return to order form after {max_retries} attempts: {str(e)}")

def go_back_to_order_form() -> None:
    """
    Goes back to the order form.
    """
    browser.page().click("button:text('Order another robot')", timeout=1000)
        
def close_annoying_modal() -> None:
    """
    Closes the annoying modal on the RobotSpareBin website.
    """
    browser.page().click("button:text('OK')")

def open_robot_order_website(config: Config) -> None:
    """
    Opens the RobotSpareBin website.

    Args:
        config (Config): The config for the RobotSpareBin Industries Inc.
    """
    browser.goto(config.robot_order_website_url)

def get_orders(config: Config) -> list[Order]:
    """
    Gets the orders from the RobotSpareBin website.

    Args:
        config (Config): The config for the RobotSpareBin Industries Inc.

    Returns:
        list[Order]: The orders from the RobotSpareBin website.
    """
    return [
        Order(
            order_number=order["Order number"],
            head=order["Head"],
            body=order["Body"],
            legs=order["Legs"],
            address=order["Address"]
        ) for order in Tables().read_table_from_csv(
            config.orders_file_name
        )
    ]

def download_file(url: str, file_name: str) -> None:
    """
    Downloads a file from the RobotSpareBin website.

    Args:
        url (str): The url of the remote file to download.
        file_name (str): The name of the file to save.
    """
    http = HTTP()
    http.download(url, file_name, overwrite=True)